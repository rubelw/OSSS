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

    def register(self, name: str, fn: RouterFn, *, description: str = "") -> None:
        key = (name or "").strip()
        if not key:
            raise RouterError("Router name cannot be empty")
        if key in self._routers:
            self.logger.warning(f"Overwriting router '{key}'")
        self._routers[key] = fn
        self._specs[key] = RouterSpec(name=key, description=description or "")
        self.logger.debug(f"Registered router '{key}'")

    def get(self, name: str) -> RouterFn:
        key = (name or "").strip()
        if key not in self._routers:
            raise RouterError(f"Unknown router: {key}")
        return self._routers[key]

    def has(self, name: str) -> bool:
        return (name or "").strip() in self._routers

    def list_names(self) -> list[str]:
        return sorted(self._routers.keys())

    def spec(self, name: str) -> Optional[RouterSpec]:
        return self._specs.get((name or "").strip())


# -----------------------------------------------------------------------------
# Safe state access helpers
# -----------------------------------------------------------------------------

def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _get_exec_state(state: OSSSState) -> Dict[str, Any]:
    # OSSSState is a TypedDict-like mapping in your codebase; still guard hard.
    try:
        return _safe_dict(state.get("execution_state"))
    except Exception:
        return {}


def _get_agent_output_meta(state: OSSSState) -> Dict[str, Any]:
    exec_state = _get_exec_state(state)
    return _safe_dict(exec_state.get("agent_output_meta"))


def _get_query_profile(state: OSSSState) -> Dict[str, Any]:
    """
    Matches your existing convention:
      execution_state.agent_output_meta._query_profile or query_profile
    """
    aom = _get_agent_output_meta(state)
    qp = aom.get("_query_profile") or aom.get("query_profile") or {}
    return _safe_dict(qp)


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

        if intent != "action":
            return False
        if action_type == "query":
            return True
        if is_query:
            return True
        if qp.get("table") or qp.get("tables") or qp.get("topic"):
            return True
        return False
    except Exception:
        return False


def router_refiner_query_or_reflect(state: OSSSState) -> str:
    """
    Router output contract:
      - "data_query"  => run data_query
      - "reflect"     => go to reflection path (critic/historian/synthesis)
    """
    return "data_query" if should_run_data_query(state) else "reflect"


def router_refiner_query_or_end(state: OSSSState) -> str:
    """
    Alternative router:
      - "data_query" => run data_query
      - "END"        => stop early
    """
    return "data_query" if should_run_data_query(state) else "END"


def router_always_synthesis(_: OSSSState) -> str:
    """Simple router for patterns that always want synthesis next."""
    return "synthesis"


def router_always_end(_: OSSSState) -> str:
    """Simple router for patterns that always want to end."""
    return "END"


def router_pick_reflection_node(state: OSSSState) -> str:
    """
    If you later store a preferred reflection agent in state, you can route it here.

    Convention supported:
      execution_state.agent_output_meta._reflection_target = "critic"|"historian"|"synthesis"
    """
    aom = _get_agent_output_meta(state)
    target = str(aom.get("_reflection_target", "")).strip().lower()
    if target in {"critic", "historian", "synthesis"}:
        return target
    return "reflect"


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
    reg.register("always_synthesis", router_always_synthesis, description="always returns synthesis")
    reg.register("always_end", router_always_end, description="always returns END")
    return reg
