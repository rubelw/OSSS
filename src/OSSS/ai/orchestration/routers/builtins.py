# OSSS/ai/orchestration/routers/builtins.py
from __future__ import annotations

from typing import Any, Dict

from OSSS.ai.observability import get_logger
from OSSS.ai.orchestration.state_schemas import OSSSState
from OSSS.ai.orchestration.routers.registry import RouterRegistry

# ✅ Best-practice: routers must ONLY treat pending_action as pending when awaiting=True
from OSSS.ai.orchestration.protocol.pending_action import (
    has_awaiting_pending_action,
    get_pending_action_type,
    get_pending_action_owner,
)

logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Small state helpers (router-safe, no planning mutation)
# -----------------------------------------------------------------------------

def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _truthy(x: Any) -> bool:
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        return x != 0
    if isinstance(x, str):
        return x.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(x)


def _get_exec_state(state: OSSSState) -> Dict[str, Any]:
    try:
        return _safe_dict(state.get("execution_state"))
    except Exception:
        return {}


def _get_agent_output_meta(state: OSSSState) -> Dict[str, Any]:
    exec_state = _get_exec_state(state)
    return _safe_dict(exec_state.get("agent_output_meta"))


def _get_query_profile(state: OSSSState) -> Dict[str, Any]:
    """
    Convention supported:
      execution_state.agent_output_meta._query_profile OR query_profile
    """
    aom = _get_agent_output_meta(state)
    qp = aom.get("_query_profile") or aom.get("query_profile") or {}
    return _safe_dict(qp)


def _get_wizard(exec_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Canonical wizard state accessor:
      execution_state["wizard"] preferred, fallback execution_state["wizard_state"]
    """
    wiz = exec_state.get("wizard")
    if isinstance(wiz, dict):
        return wiz
    wiz = exec_state.get("wizard_state")
    if isinstance(wiz, dict):
        return wiz
    return {}


def _wizard_bailed(exec_state: Dict[str, Any]) -> bool:
    return _truthy(exec_state.get("wizard_bailed"))


def _is_crud_from_wizard(wiz: Dict[str, Any]) -> bool:
    needs_crud = _truthy(wiz.get("needs_crud"))
    action = str(wiz.get("action") or "").strip().lower()
    operation = str(wiz.get("operation") or "").strip().lower()
    # Support both legacy "action" and canonical "operation"
    return bool(needs_crud or action in {"create", "update", "delete"} or operation in {"create", "update", "delete"})


def _has_pending_action_awaiting(exec_state: Dict[str, Any], *, owner: str) -> bool:
    """
    ✅ Best-practice (protocol contract):
    A pending action is pending ONLY when awaiting=True (migration-safe predicate).

    Routers must NOT treat mere presence of exec_state["pending_action"] as pending,
    because the turn controller intentionally keeps the object around after clearing
    (awaiting=False) to prevent resurrection during merges.
    """
    if not has_awaiting_pending_action(exec_state):
        return False

    # Optional: strict by owner/type so unrelated protocol owners don't block this edge.
    pa_owner = (get_pending_action_owner(exec_state) or "").strip().lower()
    if pa_owner != (owner or "").strip().lower():
        return False

    pa_type = (get_pending_action_type(exec_state) or "").strip().lower()
    # Current protocol type set (future-safe: allow empty type as interactive)
    if pa_type in {"confirm_yes_no"}:
        return True
    if not pa_type:
        return True
    return False


def _has_user_facing_data_query_answer(exec_state: Dict[str, Any]) -> bool:
    """
    True if data_query already produced a user-facing answer/result.

    ✅ Intent:
      - Prevent running FinalAgent on deterministic data_query turns (especially turn-2)
      - Treat structured data_query results as "complete enough" to END

    NOTE:
      - We keep this conservative and only check stable, canonical-ish keys.
    """
    # Canonical answer contract
    ans = exec_state.get("answer")
    if isinstance(ans, dict):
        tm = ans.get("text_markdown")
        if isinstance(tm, str) and tm.strip():
            return True

    # Compatibility bridges some pipelines/transformers use
    for k in ("text", "answer_text_markdown", "final_text_markdown", "final_markdown"):
        v = exec_state.get(k)
        if isinstance(v, str) and v.strip():
            return True

    # Structured data_query outputs
    if exec_state.get("data_query_result") is not None:
        return True

    # Sometimes the wizard stores a response-ish object under response/result
    resp = exec_state.get("response")
    if isinstance(resp, dict) and resp:
        return True

    return False


# -----------------------------------------------------------------------------
# Router output guards (critical: routers must ONLY return legal branch keys)
# -----------------------------------------------------------------------------

_ALLOWED_REFLECT = {"data_query", "reflect"}
_ALLOWED_END = {"data_query", "final", "END"}
_ALLOWED_AFTER_DQ = {"historian", "final", "END"}


def _safe_return(target: str, allowed: set[str], fallback: str) -> str:
    """
    Routers must only return legal branch keys for the conditional edge.
    If upstream accidentally sets route="refiner" (or anything else), clamp it.
    """
    t = (target or "").strip()
    if t in allowed:
        return t
    logger.error(
        "router_return_invalid_target",
        extra={"event": "router_return_invalid_target", "target": target, "allowed": sorted(allowed)},
    )
    return fallback


# -----------------------------------------------------------------------------
# Router predicates (router-only decisions among compiled nodes)
# -----------------------------------------------------------------------------

def should_run_data_query(state: OSSSState) -> bool:
    """
    Decide if data_query should execute *within a graph that already contains it*.

    NOTE:
      - This is NOT the planner’s job.
      - This is only used by conditional edges in patterns that include data_query.
    """
    qp = _get_query_profile(state)
    intent = str(qp.get("intent", "")).strip().lower()
    action_type = str(qp.get("action_type", qp.get("action", ""))).strip().lower()
    is_query = _truthy(qp.get("is_query", False))

    if intent != "action":
        return False
    if action_type == "query" or is_query:
        return True
    if qp.get("table") or qp.get("tables") or qp.get("topic"):
        return True
    return False


# -----------------------------------------------------------------------------
# Router functions (LangGraph add_conditional_edges)
# -----------------------------------------------------------------------------

def router_refiner_query_or_reflect(state: OSSSState) -> str:
    """
    Returns (LEGAL BRANCH KEYS ONLY):
      - "data_query" if query prefix OR should_run_data_query
      - "reflect" otherwise (GraphFactory maps "reflect" to critic/historian/synthesis)

    IMPORTANT:
      - Routers MUST NOT interpret yes/no wizard turns. That contract is handled
        in TurnNormalizer (planning/compile-time), not runtime branching.
      - Routers MUST ignore route_locked/route (planning inputs), and only choose
        among compiled branch keys.
    """
    try:
        q = _get_refined_query_from_state(state)
        ql = q.lower()

        # Prefix command should always go to data_query
        if ql.startswith(
            ("query ", "select ", "read ", "create ", "insert ", "update ", "modify ", "delete ", "upsert ")
        ):
            target = "data_query"
        else:
            target = "data_query" if should_run_data_query(state) else "reflect"

        logger.debug(
            "Router decision",
            extra={
                "event": "router_route",
                "router": "refiner_route_query_or_reflect",
                "target": target,
                "refined_query_preview": q[:120],
            },
        )
        return _safe_return(target, _ALLOWED_REFLECT, fallback="reflect")

    except Exception as exc:
        logger.error("Error in router_refiner_query_or_reflect", exc_info=True, extra={"error": str(exc)})
        return "reflect"


def router_refiner_query_or_end(state: OSSSState) -> str:
    try:
        exec_state = _get_exec_state(state)
        wiz = _get_wizard(exec_state)

        q = _get_refined_query_from_state(state)
        ql = q.lower().strip()

        # ✅ NEW: If wizard is done and user sends bare yes/no, treat as ack and END.
        # Prevents refiner->final from hallucinating an "answer" to "yes".
        if wiz.get("step") == "done" and ql in {"yes", "y", "no", "n"}:
            logger.info(
                "router_refiner_query_or_end_ack_after_wizard_done",
                extra={"event": "router_refiner_query_or_end_ack_after_wizard_done", "ql": ql},
            )
            return _safe_return("END", _ALLOWED_END, fallback="final")

        if ql.startswith(
            ("query ", "select ", "read ", "create ", "insert ", "update ", "modify ", "delete ", "upsert ")
        ):
            target = "data_query"
        else:
            target = "data_query" if should_run_data_query(state) else "final"

        logger.debug(
            "Router decision",
            extra={
                "event": "router_route",
                "router": "refiner_route_query_or_end",
                "target": target,
                "refined_query_preview": q[:120],
            },
        )
        return _safe_return(target, _ALLOWED_END, fallback="final")

    except Exception as exc:
        logger.error("Error in router_refiner_query_or_end", exc_info=True, extra={"error": str(exc)})
        return "final"



# -----------------------------------------------------------------------------
# ✅ Fix 1: Back-compat alias for older wiring / patterns.json
# -----------------------------------------------------------------------------

def route_after_refiner(state: OSSSState) -> str:
    """
    Back-compat router name used by graph-patterns.json / older wiring.

    Should return ONLY legal branch keys for the edge out of `refiner`
    in the `data_query` pattern: {"data_query", "final"}.

    We delegate to the canonical router implementation.
    """
    return router_refiner_query_or_end(state)


def router_pick_reflection_node(state: OSSSState) -> str:
    """
    Convention supported:
      execution_state.agent_output_meta._reflection_target = "critic"|"historian"|"synthesis"|"final"
    """
    try:
        aom = _get_agent_output_meta(state)
        raw_target = aom.get("_reflection_target", "")
        target = str(raw_target).strip().lower()

        if target in {"critic", "historian", "synthesis", "final"}:
            resolved = target
        else:
            resolved = "reflect"

        logger.debug(
            "Router decision for reflection node",
            extra={
                "event": "router_route",
                "router": "pick_reflection_node",
                "raw_target": raw_target,
                "resolved_target": resolved,
            },
        )
        return resolved
    except Exception as exc:
        logger.error("Error in router_pick_reflection_node", exc_info=True, extra={"error": str(exc)})
        return "reflect"


def router_always_synthesis(_: OSSSState) -> str:
    logger.debug("Router decision (constant)", extra={"event": "router_route", "router": "always_synthesis"})
    return "synthesis"


def router_always_end(_: OSSSState) -> str:
    logger.debug("Router decision (constant)", extra={"event": "router_route", "router": "always_end"})
    return "END"


def _get_refined_query_from_state(state: OSSSState) -> str:
    exec_state = _get_exec_state(state)

    # Prefer PR5 contract if present
    ro = exec_state.get("refiner_output")
    if isinstance(ro, dict):
        rq = ro.get("refined_query")
        if isinstance(rq, str) and rq.strip():
            return rq.strip()

    # Fallback: global refined_query
    rq2 = exec_state.get("refined_query")
    if isinstance(rq2, str) and rq2.strip():
        return rq2.strip()

    return ""


def route_after_data_query(state: OSSSState) -> str:
    """
    For graph-patterns.json 'data_query' pattern (legal keys: {"historian","final","END"}):

    ✅ Correctness goals:
      - If protocol is awaiting user input (e.g. confirm_yes_no), DO NOT run FinalAgent.
        Return END and let the API surface the prompt (query.py synthesizes prompt).
      - If the wizard prompted the user this turn, DO NOT run FinalAgent.
        Return END and let the API surface the prompt.
      - If wizard bailed, END.
      - If CRUD operation, route to historian (to narrate/validate the change).
      - Otherwise (read/query): if data_query already produced an answer/result, END (avoid FinalAgent),
        else allow final as a fallback.

    ✅ Best-practice:
      - Pending-action gating uses has_awaiting_pending_action() predicate
        (NOT presence checks).
      - Router decisions are *pure* (no state mutation).
    """
    try:
        exec_state = _get_exec_state(state)

        # ✅ HARD STOP (protocol): awaiting a yes/no (or other protocol reply)
        if _has_pending_action_awaiting(exec_state, owner="data_query"):
            logger.info(
                "route_after_data_query_end_pending_action_awaiting",
                extra={
                    "event": "route_after_data_query_end_pending_action_awaiting",
                    "pending_action_type": get_pending_action_type(exec_state),
                    "pending_action_owner": get_pending_action_owner(exec_state),
                },
            )
            return _safe_return("END", _ALLOWED_AFTER_DQ, fallback="END")

        # ✅ If we prompted this turn, END (API returns prompt text)
        if _truthy(exec_state.get("wizard_prompted_this_turn")):
            logger.info(
                "route_after_data_query_end_wizard_prompted_this_turn",
                extra={"event": "route_after_data_query_end_wizard_prompted_this_turn"},
            )
            return _safe_return("END", _ALLOWED_AFTER_DQ, fallback="END")

        # ✅ Bail short-circuit
        if _wizard_bailed(exec_state):
            logger.info(
                "route_after_data_query_end_wizard_bailed",
                extra={"event": "route_after_data_query_end_wizard_bailed"},
            )
            return _safe_return("END", _ALLOWED_AFTER_DQ, fallback="END")

        # ✅ CRUD: let historian narrate / reconcile changes
        wiz = _get_wizard(exec_state)
        if _is_crud_from_wizard(wiz):
            return _safe_return("historian", _ALLOWED_AFTER_DQ, fallback="final")

        # ✅ Read/query: if data_query already produced a user-facing answer/result, END.
        # This is the critical fix for "turn 2 still going to final".
        if _has_user_facing_data_query_answer(exec_state):
            logger.info(
                "route_after_data_query_end_answer_present",
                extra={"event": "route_after_data_query_end_answer_present"},
            )
            return _safe_return("END", _ALLOWED_AFTER_DQ, fallback="END")

        # Fallback: allow final (should be rare once data_query always populates answer/result)
        return _safe_return("final", _ALLOWED_AFTER_DQ, fallback="final")

    except Exception as exc:
        logger.error("Error in route_after_data_query", exc_info=True, extra={"error": str(exc)})
        return "final"


# -----------------------------------------------------------------------------
# Registry bootstrap
# -----------------------------------------------------------------------------

def build_default_router_registry() -> RouterRegistry:
    reg = RouterRegistry()

    reg.register(
        "refiner_route_query_or_reflect",
        router_refiner_query_or_reflect,
        description="refiner -> data_query if action+query else reflect",
    )
    reg.register(
        "refiner_route_query_or_end",
        router_refiner_query_or_end,
        description="refiner -> data_query if action+query else END",
    )

    # ✅ Fix 1: register back-compat alias name expected by older wiring
    reg.register(
        "route_after_refiner",
        route_after_refiner,
        description="BACKCOMPAT: refiner -> data_query if query/action else final",
    )

    reg.register(
        "pick_reflection_node",
        router_pick_reflection_node,
        description="reflect -> critic/historian/synthesis/final based on state hint",
    )
    reg.register(
        "always_synthesis",
        router_always_synthesis,
        description="always returns synthesis",
    )
    reg.register(
        "always_end",
        router_always_end,
        description="always returns END",
    )
    reg.register(
        "route_after_data_query",
        route_after_data_query,
        description="data_query -> historian/final/END based on wizard + answer presence",
    )

    logger.debug(
        "Built default router registry",
        extra={"event": "build_default_router_registry", "registered_routers": reg.list_names()},
    )
    return reg
