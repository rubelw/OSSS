from typing import Dict, Any, List

from dataclasses import asdict, is_dataclass  # ✅ ADD
from fastapi import APIRouter, HTTPException, Query, Request

from OSSS.ai.api.models import (
    WorkflowRequest,
    WorkflowResponse,
    WorkflowHistoryResponse,
    WorkflowHistoryItem,
    StatusResponse,
)

from OSSS.ai.api.factory import get_orchestration_api
from OSSS.ai.observability import get_logger

# ✅ NEW: public API schema + transformer
from OSSS.ai.api.schemas.query_response import QueryResponse
from OSSS.ai.api.transformers.query_transformer import (
    transform_orchestration_payload_to_query_response,
)


logger = get_logger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------
# ✅ NEW: canonical response resolution helpers (FinalAgent-first)
# ---------------------------------------------------------------------
def _resolve_question(exec_state: Dict[str, Any]) -> str:
    for k in ("user_question", "question", "query", "original_query", "raw_user_text"):
        v = exec_state.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _resolve_answer_text_markdown(exec_state: Dict[str, Any]) -> str:
    """
    Prefer what FinalAgent wrote, then fall back to other known fields.
    Only as a last resort do we echo the question.
    """
    ans = exec_state.get("answer")
    if isinstance(ans, dict):
        tm = ans.get("text_markdown")
        if isinstance(tm, str) and tm.strip():
            return tm.strip()

    # Common alternate fields some pipelines use
    for k in ("answer_text_markdown", "final_text_markdown", "final_markdown", "final"):
        v = exec_state.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    return _resolve_question(exec_state) or ""


# ---------------------------------------------------------------------
# ✅ A) Active pending-action detection (awaiting=True), not presence-based
# ---------------------------------------------------------------------
def _has_active_pending_action(exec_state: Dict[str, Any], *, pa_type: str | None = None) -> bool:
    pa = exec_state.get("pending_action")
    if not isinstance(pa, dict):
        return False
    if pa.get("awaiting") is not True:
        return False
    t = str(pa.get("type") or "").strip().lower()
    if not t:
        return False
    if pa_type is not None and t != pa_type.strip().lower():
        return False
    return True


# ---------------------------------------------------------------------
# ✅ B) Prompt-first fallback when protocol is awaiting user input
# ---------------------------------------------------------------------
def _resolve_prompt_from_pending_action(exec_state: Dict[str, Any]) -> str:
    """
    If the workflow is awaiting user input (protocol contract),
    synthesize a stable prompt so the API never "echoes the question"
    when no FinalAgent answer exists yet.
    """
    if not _has_active_pending_action(exec_state):
        return ""

    pa = exec_state.get("pending_action")
    if not isinstance(pa, dict):
        return ""

    pa_type = str(pa.get("type") or "").strip().lower()
    ctx = pa.get("context") if isinstance(pa.get("context"), dict) else {}

    # ✅ confirm_yes_no contract: deterministic prompt
    if pa_type == "confirm_yes_no":
        op = str(ctx.get("operation") or "read").strip().lower()
        table_name = str(ctx.get("table_name") or ctx.get("collection") or "").strip()
        pending_q = str(pa.get("pending_question") or "").strip()

        if table_name:
            if op == "read":
                return f"Confirm: run query on `{table_name}`? Reply **yes** or **no**."
            return f"Confirm: perform `{op}` on `{table_name}`? Reply **yes** or **no**."

        # fallback if we don't have context
        if pending_q:
            return f"Confirm: `{pending_q}`? Reply **yes** or **no**."
        return "Confirm? Reply **yes** or **no**."

    # Generic protocol fallback (in case you add other pending_action types later)
    pending_q = str(pa.get("pending_question") or "").strip()
    if pending_q:
        return pending_q
    return "I need one more input to continue."


def _coerce_mapping(obj: Any) -> Dict[str, Any]:
    # ✅ Robust: support Pydantic v2 (model_dump), dataclasses (asdict),
    # and plain dict/mapping returns.
    if hasattr(obj, "model_dump"):
        return obj.model_dump()  # type: ignore[no-any-return]
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, dict):
        return obj
    # last-resort: try to coerce mapping-like objects
    try:
        return dict(obj)  # type: ignore[arg-type]
    except TypeError:
        # ultra-safe fallback: reflect public attrs
        return {
            k: getattr(obj, k)
            for k in ("text", "execution_state", "workflow_id", "conversation_id", "correlation_id")
            if hasattr(obj, k)
        }


@router.post("/query", response_model=QueryResponse)
async def execute_query(
    http_request: Request,
    request: WorkflowRequest,
    debug: bool = Query(default=False, description="Include debug payload in response"),
) -> QueryResponse:
    try:
        # ---------------------------------------------------------
        # Log raw body + parsed agents to debug "forced agents"
        # ---------------------------------------------------------
        raw = await http_request.body()
        raw_text = raw.decode("utf-8", errors="replace")

        logger.info(
            "Received /query request",
            extra={
                "raw_body": raw_text,
                "agents": request.agents,
                "query_length": len(request.query or ""),
                "correlation_id": getattr(request, "correlation_id", None),
                "conversation_id": getattr(request, "conversation_id", None),
            },
        )

        # ---------------------------------------------------------
        # ✅ OPTION A: Normalize caller intent at API boundary
        # ---------------------------------------------------------
        exec_cfg = request.execution_config if isinstance(request.execution_config, dict) else {}
        fastpath = exec_cfg.get("graph_pattern") == "standard"

        if request.agents is not None and len(request.agents) == 0:
            request.agents = None

        if fastpath:
            request.agents = None
            if isinstance(request.execution_config, dict):
                request.execution_config.pop("agents", None)

            logger.info(
                "[api] fastpath enforced at route level",
                extra={
                    "graph_pattern": "standard",
                    "agents": None,
                    "correlation_id": getattr(request, "correlation_id", None),
                    "conversation_id": getattr(request, "conversation_id", None),
                },
            )

        # ---------------------------------------------------------
        # Execute workflow (internal schema)
        # ---------------------------------------------------------
        orchestration_api = await get_orchestration_api()
        workflow_response = await orchestration_api.execute_workflow(request)  # ✅ don’t over-constrain type here

        if not workflow_response:
            logger.error("Response is None. Unable to proceed.")
            raise HTTPException(
                status_code=500,
                detail="Workflow execution failed. No response.",
            )

        workflow_id = getattr(workflow_response, "workflow_id", None)
        if not workflow_id:
            logger.error("Response does not contain a valid workflow_id.")
            raise HTTPException(
                status_code=500,
                detail="Workflow execution failed. No workflow_id.",
            )

        logger.info(
            "Query executed successfully",
            extra={
                "workflow_id": workflow_id,
                "correlation_id": getattr(workflow_response, "correlation_id", None),
                "conversation_id": getattr(workflow_response, "conversation_id", None),
            },
        )

        # ---------------------------------------------------------
        # Transform internal workflow response -> public QueryResponse
        # ---------------------------------------------------------
        payload_dict: Dict[str, Any] = _coerce_mapping(workflow_response)

        # ---------------------------------------------------------
        # ✅ FIX: ensure the public response is built from FinalAgent output,
        # and if we're awaiting protocol input, return a prompt (not an echo).
        # ---------------------------------------------------------
        exec_state = payload_dict.get("execution_state")
        if isinstance(exec_state, dict):
            resolved_question = _resolve_question(exec_state)
            resolved_answer_md = _resolve_answer_text_markdown(exec_state)

            # ✅ A) If protocol is actively awaiting input, prefer a prompt over echo-y answers.
            prompt_md = _resolve_prompt_from_pending_action(exec_state)
            if (
                isinstance(prompt_md, str)
                and prompt_md.strip()
                and (
                    not isinstance(resolved_answer_md, str)
                    or not resolved_answer_md.strip()
                    or resolved_answer_md.strip() == (resolved_question or "").strip()
                )
            ):
                resolved_answer_md = prompt_md
                # This is a user-facing prompt turn
                exec_state["wizard_prompted_this_turn"] = True

            # 1) Ensure payload has a non-empty "question" (your raw response showed "")
            if isinstance(payload_dict.get("question"), str):
                if not payload_dict["question"].strip() and resolved_question:
                    payload_dict["question"] = resolved_question
            elif resolved_question:
                payload_dict["question"] = resolved_question

            # 2) Ensure execution_state carries canonical answer shape
            ans = exec_state.get("answer")
            if not isinstance(ans, dict):
                ans = {}
                exec_state["answer"] = ans

            if isinstance(resolved_answer_md, str) and resolved_answer_md.strip():
                ans["text_markdown"] = resolved_answer_md

            # 3) Also set top-level "text" as a compatibility bridge (many transformers use it)
            if isinstance(payload_dict.get("text"), str):
                if not payload_dict["text"].strip() and resolved_answer_md:
                    payload_dict["text"] = resolved_answer_md
            elif resolved_answer_md:
                payload_dict["text"] = resolved_answer_md

            # 4) Write back execution_state (in case payload_dict had a shallow copy)
            payload_dict["execution_state"] = exec_state

            logger.warning(
                "[api.query] resolved response fields",
                extra={
                    "question_preview": (payload_dict.get("question") or "")[:120],
                    "answer_preview": (payload_dict.get("text") or "")[:120],
                    # ✅ A) "pending" should mean actively awaiting, not merely present
                    "has_pending_action": _has_active_pending_action(exec_state),
                    "pending_action_type": (exec_state.get("pending_action") or {}).get("type")
                    if isinstance(exec_state.get("pending_action"), dict)
                    else None,
                    "pending_action_awaiting": (exec_state.get("pending_action") or {}).get("awaiting") is True
                    if isinstance(exec_state.get("pending_action"), dict)
                    else None,
                },
            )

        public_response: QueryResponse = transform_orchestration_payload_to_query_response(
            payload_dict,
            include_debug=debug,
        )

        return public_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Workflow execution failed",
                "message": str(e),
                "type": type(e).__name__,
            },
        )
