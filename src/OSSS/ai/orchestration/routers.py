"""
OSSS LangGraph orchestration routers.

This module provides:
- A small RouterRegistry for named, testable router functions
- Built-in routers used by graph patterns (graph-patterns.json)
- Helpers for reading routing signals from OSSSState / execution_state

Router contract (LangGraph add_conditional_edges):
    router(state: OSSSState) -> str

Returned string is mapped by GraphFactory to a destination node key, e.g.:
- "data_query" -> node "data_query"
- "reflect"    -> first available reflection node (critic/historian/synthesis)
- "END"        -> END
- any node name (e.g. "critic") if you want direct routing
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, List

from langgraph.graph import END  # noqa: F401  (imported for type parity / documentation)

from OSSS.ai.orchestration.state_schemas import OSSSState
from OSSS.ai.observability import get_logger


RouterFn = Callable[[OSSSState], str]

# Module-level logger for router observability
logger = get_logger(__name__)


@dataclass(frozen=True)
class RoutingResult:
    agents: List[str]                 # final agents_to_run
    pattern: str = "standard"         # graph pattern name
    meta: Dict[str, Any] = None       # debugging


class RouterError(Exception):
    """Raised for router registry or execution errors."""


@dataclass(frozen=True)
class RouterSpec:
    """
    Optional metadata for introspection / docs / validation.

    You can expand this later to include:
      - allowed_outputs
      - description
      - required_state_paths
    """
    name: str
    description: str = ""


class RouterRegistry:
    """
    Central registry of named router functions.

    GraphFactory / PatternSpec refers to routers by string name.
    """

    def __init__(self) -> None:
        self._routers: Dict[str, RouterFn] = {}
        self._specs: Dict[str, RouterSpec] = {}
        self.logger = get_logger(f"{__name__}.RouterRegistry")
        self.logger.debug(
            "Initialized RouterRegistry",
            extra={"event": "router_registry_init"},
        )

    def register(self, name: str, fn: RouterFn, *, description: str = "") -> None:
        key = (name or "").strip()
        if not key:
            self.logger.error(
                "Attempted to register router with empty name",
                extra={"event": "router_register_error"},
            )
            raise RouterError("Router name cannot be empty")

        if key in self._routers:
            self.logger.warning(
                "Overwriting existing router",
                extra={"event": "router_register_overwrite", "router_name": key},
            )

        self._routers[key] = fn
        self._specs[key] = RouterSpec(name=key, description=description or "")

        self.logger.debug(
            "Registered router",
            extra={
                "event": "router_registered",
                "router_name": key,
                "description": description or "",
                "available_routers": sorted(self._routers.keys()),
            },
        )

    def get(self, name: str) -> RouterFn:
        key = (name or "").strip()
        if key not in self._routers:
            self.logger.error(
                "Unknown router requested",
                extra={"event": "router_lookup_failed", "router_name": key},
            )
            raise RouterError(f"Unknown router: {key}")

        self.logger.debug(
            "Router lookup successful",
            extra={"event": "router_lookup", "router_name": key},
        )
        return self._routers[key]

    def has(self, name: str) -> bool:
        key = (name or "").strip()
        exists = key in self._routers
        self.logger.debug(
            "Router existence check",
            extra={"event": "router_has", "router_name": key, "exists": exists},
        )
        return exists

    def list_names(self) -> list[str]:
        names = sorted(self._routers.keys())
        self.logger.debug(
            "Listing routers",
            extra={"event": "router_list", "router_count": len(names)},
        )
        return names

    def spec(self, name: str) -> Optional[RouterSpec]:
        key = (name or "").strip()
        spec = self._specs.get(key)
        self.logger.debug(
            "Router spec lookup",
            extra={
                "event": "router_spec_lookup",
                "router_name": key,
                "found": spec is not None,
            },
        )
        return spec


# -----------------------------------------------------------------------------
# Safe state access helpers
# -----------------------------------------------------------------------------

def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _get_exec_state(state: OSSSState) -> Dict[str, Any]:
    # OSSSState is a TypedDict-like mapping in your codebase; still guard hard.
    try:
        exec_state = _safe_dict(state.get("execution_state"))
        logger.debug(
            "Fetched execution_state from OSSSState",
            extra={
                "event": "get_exec_state",
                # Avoid logging full state; just note presence / keys.
                "has_execution_state": bool(exec_state),
                "exec_state_keys": list(exec_state.keys()) if exec_state else [],
            },
        )
        return exec_state
    except Exception as exc:
        logger.error(
            "Failed to fetch execution_state from OSSSState",
            exc_info=True,
            extra={"event": "get_exec_state_error", "error_type": type(exc).__name__},
        )
        return {}


def _get_agent_output_meta(state: OSSSState) -> Dict[str, Any]:
    exec_state = _get_exec_state(state)
    aom = _safe_dict(exec_state.get("agent_output_meta"))
    logger.debug(
        "Fetched agent_output_meta",
        extra={
            "event": "get_agent_output_meta",
            "has_agent_output_meta": bool(aom),
            "agent_output_meta_keys": list(aom.keys()) if aom else [],
        },
    )
    return aom


def _get_query_profile(state: OSSSState) -> Dict[str, Any]:
    """
    Matches your existing convention:
      execution_state.agent_output_meta._query_profile or query_profile
    """
    aom = _get_agent_output_meta(state)
    qp = aom.get("_query_profile") or aom.get("query_profile") or {}
    qp = _safe_dict(qp)

    logger.debug(
        "Fetched query_profile",
        extra={
            "event": "get_query_profile",
            "has_query_profile": bool(qp),
            "query_profile_keys": list(qp.keys()) if qp else [],
        },
    )
    return qp


# -----------------------------------------------------------------------------
# NEW helpers for data_query → CRUD routing
# -----------------------------------------------------------------------------

def _get_available_agents_from_state(state: OSSSState) -> List[str]:
    """
    Recover the list of agents that actually exist in this compiled graph.

    We look (in order) at:
      - state.execution_state.planned_agents / agents_to_run
      - top-level state.planned_agents / agents_to_run / agents_requested
    """
    agents: List[str] = []

    try:
        exec_state = _get_exec_state(state)
        if exec_state:
            planned = exec_state.get("planned_agents") or exec_state.get("agents_to_run")
            if isinstance(planned, list):
                agents = [str(a) for a in planned]

        if not agents and isinstance(state, dict):
            for key in ("planned_agents", "agents_to_run", "agents_requested"):
                val = state.get(key)
                if isinstance(val, list):
                    agents = [str(a) for a in val]
                    break

        # Deduplicate while preserving order
        seen: set[str] = set()
        deduped: List[str] = []
        for a in agents:
            if a not in seen:
                seen.add(a)
                deduped.append(a)

        logger.debug(
            "Resolved available agents from state",
            extra={
                "event": "get_available_agents_from_state",
                "available_agents": deduped,
            },
        )
        return deduped

    except Exception as exc:
        logger.error(
            "Error resolving available agents from state",
            exc_info=True,
            extra={
                "event": "get_available_agents_from_state_error",
                "error_type": type(exc).__name__,
            },
        )
        return []


def _extract_data_query_wizard_state(state: OSSSState) -> Dict[str, Any] | None:
    """
    Best-effort extraction of DataQuery CRUD wizard_state.

    We check (in order / new convention first):
      - execution_state.wizard
      - execution_state.wizard_state (legacy)
      - state.wizard (legacy top-level)
      - state.wizard_state (legacy top-level)
      - state.data_query.wizard_state (older shapes)
    """
    try:
        if not isinstance(state, dict):
            return None

        exec_state = _get_exec_state(state)

        # ✅ NEW canonical location
        if exec_state:
            wiz = exec_state.get("wizard")
            if isinstance(wiz, dict):
                logger.debug(
                    "Found wizard in execution_state",
                    extra={
                        "event": "extract_data_query_wizard_state",
                        "source": "execution_state.wizard",
                        "wizard_keys": list(wiz.keys()),
                    },
                )
                return wiz

            # Legacy key support
            wiz = exec_state.get("wizard_state")
            if isinstance(wiz, dict):
                logger.debug(
                    "Found wizard_state in execution_state",
                    extra={
                        "event": "extract_data_query_wizard_state",
                        "source": "execution_state.wizard_state",
                        "wizard_keys": list(wiz.keys()),
                    },
                )
                return wiz

        # Top-level, for older shapes
        wiz = state.get("wizard")
        if isinstance(wiz, dict):
            logger.debug(
                "Found wizard at top-level state",
                extra={
                    "event": "extract_data_query_wizard_state",
                    "source": "state.wizard",
                    "wizard_keys": list(wiz.keys()),
                },
            )
            return wiz

        wiz = state.get("wizard_state")
        if isinstance(wiz, dict):
            logger.debug(
                "Found wizard_state at top-level state",
                extra={
                    "event": "extract_data_query_wizard_state",
                    "source": "state.wizard_state",
                    "wizard_keys": list(wiz.keys()),
                },
            )
            return wiz

        # Very old layout: state["data_query"]["wizard_state"]
        dq_state = state.get("data_query")
        if isinstance(dq_state, dict):
            wiz = dq_state.get("wizard_state")
            if isinstance(wiz, dict):
                logger.debug(
                    "Found wizard_state under data_query",
                    extra={
                        "event": "extract_data_query_wizard_state",
                        "source": "data_query.wizard_state",
                        "wizard_keys": list(wiz.keys()),
                    },
                )
                return wiz

        logger.debug(
            "No wizard or wizard_state found for data_query",
            extra={"event": "extract_data_query_wizard_state", "source": "none"},
        )
        return None

    except Exception as exc:
        logger.error(
            "Error extracting data_query wizard_state",
            exc_info=True,
            extra={
                "event": "extract_data_query_wizard_state_error",
                "error_type": type(exc).__name__,
            },
        )
        return None



def _truthy(x: Any) -> bool:
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        return x != 0
    if isinstance(x, str):
        return x.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(x)


# -----------------------------------------------------------------------------
# Core routing logic (small, composable predicates)
# -----------------------------------------------------------------------------

def should_run_data_query(state: OSSSState) -> bool:
    """
    Decide if data_query should execute.

    Current heuristic (you can tighten later):
      - intent == "action"
      - and (action_type == "query" OR is_query OR table/tables/topic present)
    """
    try:
        qp = _get_query_profile(state)
        intent = str(qp.get("intent", "")).lower()
        action_type = str(qp.get("action_type", qp.get("action", ""))).lower()
        is_query = _truthy(qp.get("is_query", False))

        decision = False
        reason: str = ""

        if intent != "action":
            decision = False
            reason = "intent_not_action"
        elif action_type == "query":
            decision = True
            reason = "action_type_query"
        elif is_query:
            decision = True
            reason = "is_query_flag"
        elif qp.get("table") or qp.get("tables") or qp.get("topic"):
            decision = True
            reason = "table_or_topic_present"
        else:
            decision = False
            reason = "no_query_signals"

        logger.debug(
            "Evaluated should_run_data_query",
            extra={
                "event": "routing_decision",
                "router": "should_run_data_query",
                "decision": decision,
                "reason": reason,
                "intent": intent,
                "action_type": action_type,
                "is_query": is_query,
                "has_table": bool(qp.get("table")),
                "has_tables": bool(qp.get("tables")),
                "has_topic": bool(qp.get("topic")),
            },
        )
        return decision
    except Exception as exc:
        logger.error(
            "Error while evaluating should_run_data_query",
            exc_info=True,
            extra={
                "event": "routing_decision_error",
                "router": "should_run_data_query",
                "error_type": type(exc).__name__,
            },
        )
        return False


def router_refiner_query_or_reflect(state: OSSSState) -> str:
    """
    Router output contract:
      - "data_query"  => run data_query
      - "reflect"     => go to reflection path (critic/historian/synthesis)
    """
    try:
        target = "data_query" if should_run_data_query(state) else "reflect"
        logger.debug(
            "Router decision",
            extra={
                "event": "router_route",
                "router": "refiner_route_query_or_reflect",
                "target": target,
            },
        )
        return target
    except Exception as exc:
        logger.error(
            "Error in router_refiner_query_or_reflect",
            exc_info=True,
            extra={
                "event": "router_error",
                "router": "refiner_route_query_or_reflect",
                "error_type": type(exc).__name__,
            },
        )
        return "reflect"


def router_refiner_query_or_end(state: OSSSState) -> str:
    """
    Alternative router:
      - "data_query" => run data_query
      - "END"        => stop early
    """
    try:
        target = "data_query" if should_run_data_query(state) else "END"
        logger.debug(
            "Router decision",
            extra={
                "event": "router_route",
                "router": "refiner_route_query_or_end",
                "target": target,
            },
        )
        return target
    except Exception as exc:
        logger.error(
            "Error in router_refiner_query_or_end",
            exc_info=True,
            extra={
                "event": "router_error",
                "router": "refiner_route_query_or_end",
                "error_type": type(exc).__name__,
            },
        )
        return "END"


def router_always_synthesis(_: OSSSState) -> str:
    """Simple router for patterns that always want synthesis next."""
    target = "synthesis"
    logger.debug(
        "Router decision (constant)",
        extra={
            "event": "router_route",
            "router": "always_synthesis",
            "target": target,
        },
    )
    return target


def router_always_end(_: OSSSState) -> str:
    """Simple router for patterns that always want to end."""
    target = "END"
    logger.debug(
        "Router decision (constant)",
        extra={
            "event": "router_route",
            "router": "always_end",
            "target": target,
        },
    )
    return target


def router_pick_reflection_node(state: OSSSState) -> str:
    """
    If you later store a preferred reflection agent in state, you can route it here.

    Convention supported:
      execution_state.agent_output_meta._reflection_target = "critic"|"historian"|"synthesis"
    """
    try:
        aom = _get_agent_output_meta(state)
        raw_target = aom.get("_reflection_target", "")
        target = str(raw_target).strip().lower()

        # Normalize to actual node keys; you might adapt this as your graph evolves.
        if target in {"critic", "historian", "synthesis"}:
            resolved = target
        elif target == "final":
            resolved = "final"
        else:
            resolved = "reflect"

        logger.debug(
            "Router decision for reflection node",
            extra={
                "event": "router_route",
                "router": "pick_reflection_node",
                "raw_target": raw_target,
                "normalized_target": target,
                "resolved_target": resolved,
            },
        )
        return resolved
    except Exception as exc:
        logger.error(
            "Error in router_pick_reflection_node",
            exc_info=True,
            extra={
                "event": "router_error",
                "router": "pick_reflection_node",
                "error_type": type(exc).__name__,
            },
        )
        return "reflect"


# -----------------------------------------------------------------------------
# NEW: route_after_data_query for CRUD / wizard flows
# -----------------------------------------------------------------------------

def route_after_data_query(state: OSSSState) -> str:
    """
    Decide where to go after `data_query`.

    Wizard behavior:

    - While the CRUD wizard is in progress (pending_action is set),
      ALWAYS return "END" so the HTTP round-trip can complete and
      the user can respond to the wizard prompt.

    - Only consider routing to follow-on agents (historian/final)
      once there is NO pending_action.

    Pattern behavior:

    - For the pure `data_query` graph pattern, we never route to `final`
      because that node usually is not part of the compiled graph.
      In that case we simply END once data_query is done.

    Fallback is always "END" on errors.
    """
    try:
        exec_state = _get_exec_state(state)
        graph_pattern = str(exec_state.get("graph_pattern") or "").lower()

        # Wizard state written by DataQueryAgent
        wizard_state = _extract_data_query_wizard_state(state) or {}
        operation = str(wizard_state.get("operation") or "").lower()
        pending_action = str(wizard_state.get("pending_action") or "").lower()

        # All CRUD-style ops (including read/query flows)
        crud_ops = {"create", "read", "update", "delete", "patch"}
        is_crud = operation in crud_ops

        # What agents *this* graph actually planned to run
        available_agents = _get_available_agents_from_state(state)

        logger.debug(
            "[router:route_after_data_query] routing decision context",
            extra={
                "event": "router_route",
                "router": "route_after_data_query",
                "intent": operation,
                "action_type": operation,
                "pending_action": pending_action,
                "is_crud": is_crud,
                "graph_pattern": graph_pattern,
                "available_agents": available_agents,
            },
        )

        # 1) Wizard still in progress → keep it alive and wait for next turn
        if pending_action:
            logger.debug(
                "[router:route_after_data_query] Wizard pending; ending workflow for user follow-up",
                extra={
                    "event": "router_route_wizard_pending",
                    "pending_action": pending_action,
                },
            )
            return "END"

        # 2) Pure data_query pattern: we don't have a follow-on final node
        if graph_pattern == "data_query":
            logger.debug(
                "[router:route_after_data_query] data_query pattern; no follow-on node, ending",
                extra={
                    "event": "router_route_data_query_pattern_end",
                },
            )
            return "END"

        # 3) Multi-agent patterns: wizard is complete; optionally hand off
        decision = "END"
        if is_crud:
            if "historian" in available_agents:
                decision = "historian"
            elif "final" in available_agents:
                decision = "final"

        logger.debug(
            "[router:route_after_data_query] evaluated",
            extra={
                "event": "router_route",
                "router": "route_after_data_query",
                "intent": operation,
                "action_type": operation,
                "pending_action": pending_action,
                "is_crud": is_crud,
                "available_agents": available_agents,
                "decision": decision,
            },
        )
        return decision

    except Exception as exc:
        logger.error(
            "Error in route_after_data_query",
            exc_info=True,
            extra={
                "event": "router_error",
                "router": "route_after_data_query",
                "error_type": type(exc).__name__,
            },
        )
        return "END"



# -----------------------------------------------------------------------------
# Registry bootstrap
# -----------------------------------------------------------------------------

def build_default_router_registry() -> RouterRegistry:
    """
    Create a registry with the default routers.

    GraphFactory can either:
      - call this and use it directly, OR
      - call RouterRegistry() then register manually
    """
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
    reg.register(
        "pick_reflection_node",
        router_pick_reflection_node,
        description="reflect -> critic/historian/synthesis based on state hint",
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
        description="data_query -> historian/final/END based on CRUD wizard_state",
    )

    logger.debug(
        "Built default router registry",
        extra={
            "event": "build_default_router_registry",
            "registered_routers": reg.list_names(),
        },
    )
    return reg
