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
        # ✅ Robust: support Pydantic v2 (model_dump), dataclasses (asdict),
        # and plain dict/mapping returns.
        if hasattr(workflow_response, "model_dump"):
            payload_dict: Dict[str, Any] = workflow_response.model_dump()
        elif is_dataclass(workflow_response):
            payload_dict = asdict(workflow_response)
        elif isinstance(workflow_response, dict):
            payload_dict = workflow_response
        else:
            # last-resort: try to coerce mapping-like objects
            try:
                payload_dict = dict(workflow_response)  # type: ignore[arg-type]
            except TypeError:
                # ultra-safe fallback: reflect public attrs
                payload_dict = {
                    k: getattr(workflow_response, k)
                    for k in ("text", "execution_state", "workflow_id", "conversation_id", "correlation_id")
                    if hasattr(workflow_response, k)
                }

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
