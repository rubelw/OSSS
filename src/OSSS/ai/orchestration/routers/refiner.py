# OSSS.ai.orchestration.routers.refiner

from __future__ import annotations

from typing import Any

from OSSS.ai.orchestration.state_schemas import OSSSState
from OSSS.ai.observability import get_logger

from OSSS.ai.orchestration.routers.constants import ROUTE_DATA_QUERY, ROUTE_FINAL, ROUTE_REFLECT, ROUTE_END
from OSSS.ai.orchestration.routers.helpers import (
    get_exec_state,
    get_query_profile,
    truthy,
)

# ✅ Fix 2: keep legacy import path working for RouterRegistry bootstrap
# (it tries: OSSS.ai.orchestration.routers.refiner.refiner_route_query_or_end)
from OSSS.ai.orchestration.routers.builtins import router_refiner_query_or_end as _builtin_router_refiner_query_or_end

logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Predicates (pure helpers specific to refiner-stage branching)
# -----------------------------------------------------------------------------

def should_run_data_query_after_refiner(state: OSSSState) -> bool:
    """
    Decide whether the next step after refiner should be data_query.

    Keep this conservative and *state-derived* only.
    No planning mutation, no graph assumptions.

    Sources of truth (in priority order):
      1) routing_signals (if planner attached them)
      2) query_profile heuristic (legacy)
    """
    exec_state = get_exec_state(state)

    # 1) Prefer routing_signals if present (produced during planning)
    signals = exec_state.get("routing_signals")
    if isinstance(signals, dict):
        target = str(signals.get("target") or "").strip().lower()
        locked = truthy(signals.get("locked"))
        if locked and target == ROUTE_DATA_QUERY:
            return True
        # If it's explicitly locked away from data_query, honor it
        if locked and target and target != ROUTE_DATA_QUERY:
            return False

    # 2) Fall back to query_profile heuristic (what your old routers used)
    qp = get_query_profile(state)
    intent = str(qp.get("intent") or "").strip().lower()
    action_type = str(qp.get("action_type") or qp.get("action") or "").strip().lower()
    is_query = truthy(qp.get("is_query"))

    if intent != "action":
        return False
    if action_type == "query":
        return True
    if is_query:
        return True
    if qp.get("table") or qp.get("tables") or qp.get("topic"):
        return True

    return False


def should_end_after_refiner(state: OSSSState) -> bool:
    """
    Optional: for patterns that allow early termination.
    Usually False unless you have explicit state flags for it.
    """
    exec_state = get_exec_state(state)
    return truthy(exec_state.get("end_after_refiner"))


def _planned_includes_final(exec_state: dict[str, Any]) -> bool:
    """
    ✅ Invariant helper: if planning says final should run, router must not terminate early.
    """
    planned = exec_state.get("planned_agents") or []
    if not isinstance(planned, list):
        return False
    planned_lc = {str(a).strip().lower() for a in planned if str(a).strip()}
    return "final" in planned_lc


# -----------------------------------------------------------------------------
# ✅ Fix 2: legacy symbol expected by RouterRegistry bootstrap + older imports
# -----------------------------------------------------------------------------

def refiner_route_query_or_end(state: OSSSState) -> str:
    """
    Legacy export name used by RouterRegistry bootstrap and older wiring.

    Must return only legal branch keys for the `refiner` conditional edge
    in the `data_query` pattern: {"data_query", "final"}.

    Delegate to the canonical implementation in routers.builtins.
    """
    return _builtin_router_refiner_query_or_end(state)


# -----------------------------------------------------------------------------
# Routers (LangGraph conditional router contract: router(state) -> str)
# -----------------------------------------------------------------------------

def route_refiner_query_or_final(state: OSSSState) -> str:
    """
    Router for patterns where refiner branches:
      - data_query if strong signals
      - otherwise final
    """
    try:
        target = ROUTE_DATA_QUERY if should_run_data_query_after_refiner(state) else ROUTE_FINAL
        logger.debug(
            "refiner router: query_or_final",
            extra={"event": "router_route", "router": "route_refiner_query_or_final", "target": target},
        )
        return target
    except Exception as exc:
        logger.error(
            "refiner router failed: query_or_final",
            exc_info=True,
            extra={"event": "router_error", "router": "route_refiner_query_or_final", "error": str(exc)},
        )
        return ROUTE_FINAL


def route_refiner_query_or_reflect(state: OSSSState) -> str:
    """
    Router for patterns where refiner branches:
      - data_query if strong signals
      - otherwise reflect (a virtual key resolved by GraphFactory)
    """
    try:
        target = ROUTE_DATA_QUERY if should_run_data_query_after_refiner(state) else ROUTE_REFLECT
        logger.debug(
            "refiner router: query_or_reflect",
            extra={"event": "router_route", "router": "route_refiner_query_or_reflect", "target": target},
        )
        return target
    except Exception as exc:
        logger.error(
            "refiner router failed: query_or_reflect",
            exc_info=True,
            extra={"event": "router_error", "router": "route_refiner_query_or_reflect", "error": str(exc)},
        )
        return ROUTE_REFLECT


def route_refiner_query_or_end(state: OSSSState) -> str:
    """
    Router for patterns where refiner branches:
      - data_query if strong signals
      - otherwise END (stop)

    ✅ Planned-final invariant:
      If exec_state indicates planned_agents includes "final",
      this router MUST NOT return END. It should return "final" instead.
    """
    try:
        exec_state = get_exec_state(state)

        if should_run_data_query_after_refiner(state):
            computed_target = ROUTE_DATA_QUERY
        else:
            computed_target = ROUTE_END if should_end_after_refiner(state) else ROUTE_END

        # ✅ Guard: if final is planned, do NOT terminate early
        if _planned_includes_final(exec_state):
            # Handle both string "END" and constant-like values
            if str(computed_target).strip().upper() == "END" or computed_target == ROUTE_END:
                logger.debug(
                    "refiner router: query_or_end (guarded -> final)",
                    extra={
                        "event": "router_guard",
                        "router": "route_refiner_query_or_end",
                        "computed_target": str(computed_target),
                        "forced_target": ROUTE_FINAL,
                        "planned_agents": exec_state.get("planned_agents"),
                    },
                )
                return ROUTE_FINAL

        logger.debug(
            "refiner router: query_or_end",
            extra={"event": "router_route", "router": "route_refiner_query_or_end", "target": computed_target},
        )
        return computed_target
    except Exception as exc:
        logger.error(
            "refiner router failed: query_or_end",
            exc_info=True,
            extra={"event": "router_error", "router": "route_refiner_query_or_end", "error": str(exc)},
        )
        # If final is planned, fail-safe to final; otherwise allow end.
        try:
            exec_state = get_exec_state(state)
            if _planned_includes_final(exec_state):
                return ROUTE_FINAL
        except Exception:
            pass
        return ROUTE_END
