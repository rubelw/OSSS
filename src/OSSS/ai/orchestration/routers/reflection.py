# OSSS.ai.orchestration.routers.reflection

from __future__ import annotations

from typing import Any, Iterable, Optional

from OSSS.ai.orchestration.state_schemas import OSSSState
from OSSS.ai.observability import get_logger

from OSSS.ai.orchestration.routers.constants import (
    ROUTE_CRITIC,
    ROUTE_HISTORIAN,
    ROUTE_SYNTHESIS,
    ROUTE_FINAL,
    ROUTE_REFLECT,
)
from OSSS.ai.orchestration.routers.helpers import (
    get_exec_state,
    get_agent_output_meta,
    truthy,
)

logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _normalize_node_name(x: Any) -> str:
    return str(x or "").strip().lower().replace("-", "_")


def _as_set(values: Any) -> set[str]:
    if isinstance(values, (list, tuple, set)):
        return {str(v).strip().lower() for v in values if str(v).strip()}
    return set()


def _candidate_order(default_order: Optional[Iterable[str]] = None) -> list[str]:
    return list(default_order or [ROUTE_CRITIC, ROUTE_HISTORIAN, ROUTE_SYNTHESIS])


# -----------------------------------------------------------------------------
# Predicates
# -----------------------------------------------------------------------------

def should_run_historian_reflection(state: OSSSState) -> bool:
    """
    Reflection-time historian heuristic.

    Keep it strict and stable. Typical signals:
      - execution_state["historian_enabled"] (optional)
      - execution_state["suppress_history"] (wizard rejects, etc.)
    """
    exec_state = get_exec_state(state)

    if truthy(exec_state.get("suppress_history")):
        return False

    # allow explicit toggle
    if "historian_enabled" in exec_state:
        return truthy(exec_state.get("historian_enabled"))

    # default: if you have no explicit policy, allow historian
    return True


def should_run_critic_reflection(state: OSSSState) -> bool:
    """
    Reflection-time critic heuristic.
    Useful if you want to disable critic for some flows.
    """
    exec_state = get_exec_state(state)
    if "critic_enabled" in exec_state:
        return truthy(exec_state.get("critic_enabled"))
    return True


def should_run_synthesis_reflection(state: OSSSState) -> bool:
    exec_state = get_exec_state(state)
    if "synthesis_enabled" in exec_state:
        return truthy(exec_state.get("synthesis_enabled"))
    return True


# -----------------------------------------------------------------------------
# Router(s)
# -----------------------------------------------------------------------------

def route_reflect_pick_node(state: OSSSState) -> str:
    """
    Router for resolving the virtual 'reflect' target into a concrete node.

    Priority:
      1) explicit hint: execution_state.agent_output_meta._reflection_target
      2) skip_agents filtering
      3) simple enable/disable heuristics
      4) fallback to final

    IMPORTANT:
      - This function must NOT assume nodes exist.
      - GraphFactory should still validate the return value exists in compiled nodes,
        and if not, treat it as ROUTE_FINAL.
    """
    try:
        exec_state = get_exec_state(state)
        aom = get_agent_output_meta(state)

        # Allow explicit override from upstream
        hinted = _normalize_node_name(aom.get("_reflection_target") or aom.get("reflection_target"))
        if hinted in {ROUTE_CRITIC, ROUTE_HISTORIAN, ROUTE_SYNTHESIS, ROUTE_FINAL}:
            logger.debug(
                "reflection router: using explicit target",
                extra={"event": "router_route", "router": "route_reflect_pick_node", "target": hinted},
            )
            return hinted

        skip = _as_set(exec_state.get("skip_agents"))
        # Evaluate in stable order
        for cand in _candidate_order():
            if cand in skip:
                continue
            if cand == ROUTE_HISTORIAN and not should_run_historian_reflection(state):
                continue
            if cand == ROUTE_CRITIC and not should_run_critic_reflection(state):
                continue
            if cand == ROUTE_SYNTHESIS and not should_run_synthesis_reflection(state):
                continue

            logger.debug(
                "reflection router: selected candidate",
                extra={"event": "router_route", "router": "route_reflect_pick_node", "target": cand, "skip": list(skip)},
            )
            return cand

        # Nothing eligible: safest fallback
        logger.debug(
            "reflection router: no eligible reflection node; falling back to final",
            extra={"event": "router_route", "router": "route_reflect_pick_node", "target": ROUTE_FINAL, "skip": list(skip)},
        )
        return ROUTE_FINAL

    except Exception as exc:
        logger.error(
            "reflection router failed",
            exc_info=True,
            extra={"event": "router_error", "router": "route_reflect_pick_node", "error": str(exc)},
        )
        return ROUTE_FINAL
