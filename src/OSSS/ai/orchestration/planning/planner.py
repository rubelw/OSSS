# OSSS/ai/orchestration/planning/planner.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

from OSSS.ai.observability import get_logger
from .plan import ExecutionPlan

logger = get_logger(__name__)

# Contract Superset Mode: canonical contract patterns only
_CANONICAL_PATTERNS: tuple[str, ...] = ("standard", "data_query")


class PlanningRule(Protocol):
    """
    STRICT (no backwards compatibility):

    Every rule MUST implement:

        apply(*, exec_state: dict[str, Any], request: dict[str, Any]) -> ExecutionPlan | None
    """

    def apply(self, *, exec_state: Dict[str, Any], request: Dict[str, Any]) -> Optional[ExecutionPlan]:
        ...


def _require_bool_or_none(v: Any, name: str) -> Optional[bool]:
    if v is None:
        return None
    if not isinstance(v, bool):
        raise TypeError(f"exec_state[{name!r}] must be bool when provided")
    return v


def _enforce_plan_invariants(exec_state: Dict[str, Any], plan: ExecutionPlan) -> ExecutionPlan:
    """
    STRICT invariants (Contract Superset Mode):

    - plan.pattern MUST be one of the canonical contract patterns: "standard" | "data_query"
      (pattern names must exist in graph-patterns.json / PatternService).
    - plan.agents MUST be non-empty list[str], already normalized (lowercase, non-empty).
    - plan.entry_point MUST be non-empty and be in plan.agents.
    - If routing is locked to 'data_query' (either in exec_state OR the plan),
      then:
        - 'data_query' MUST be in plan.agents
        - plan.pattern MUST be 'data_query' (contract that includes that node)
    - IMPORTANT: This function preserves all plan fields (skip_agents/resume_query/route/meta).
    """
    if plan is None:
        raise ValueError("ExecutionPlan is required")

    pattern = getattr(plan, "pattern", None)
    agents = getattr(plan, "agents", None)
    entry_point = getattr(plan, "entry_point", None)

    if not isinstance(pattern, str) or not pattern.strip():
        raise TypeError("ExecutionPlan.pattern must be a non-empty str")
    pattern = pattern.strip().lower()

    if pattern == "superset":
        raise ValueError(
            "Contract Superset Mode: 'superset' is NOT a valid pattern name. "
            "Use pattern='standard' or 'data_query' and express superset compilation via "
            "compile_variant='superset' (or agents_superset=True)."
        )
    if pattern not in _CANONICAL_PATTERNS:
        raise ValueError(f"Unknown ExecutionPlan.pattern: {pattern!r}. Allowed: {list(_CANONICAL_PATTERNS)}")

    if not isinstance(agents, list) or not agents:
        raise TypeError("ExecutionPlan.agents must be a non-empty list[str]")
    if not all(isinstance(a, str) and a.strip() for a in agents):
        raise TypeError("ExecutionPlan.agents must contain only non-empty str")

    # normalize agents (lowercase, strip) + de-dupe preserve order
    norm_agents: list[str] = []
    seen: set[str] = set()
    for a in agents:
        s = a.strip().lower()
        if s and s not in seen:
            seen.add(s)
            norm_agents.append(s)

    if not norm_agents:
        raise ValueError("ExecutionPlan.agents normalized to empty list")

    if not isinstance(entry_point, str) or not entry_point.strip():
        raise TypeError("ExecutionPlan.entry_point must be a non-empty str")
    entry_point = entry_point.strip().lower()

    if entry_point not in norm_agents:
        raise ValueError(f"ExecutionPlan.entry_point {entry_point!r} must be in ExecutionPlan.agents")

    # Determine "effective" lock+route (plan overrides exec_state if set)
    exec_route_locked = _require_bool_or_none(exec_state.get("route_locked"), "route_locked")
    exec_route = exec_state.get("route")
    if exec_route is not None and not isinstance(exec_route, str):
        raise TypeError("exec_state['route'] must be str when provided")

    plan_route_locked = getattr(plan, "route_locked", False)
    if plan_route_locked is not None and not isinstance(plan_route_locked, bool):
        raise TypeError("ExecutionPlan.route_locked must be bool")

    plan_route = getattr(plan, "route", None)
    if plan_route is not None and not isinstance(plan_route, str):
        raise TypeError("ExecutionPlan.route must be str when provided")

    # NOTE: historical behavior: if plan.route is set, trust plan.route_locked; otherwise use exec_state lock
    effective_locked = bool(plan_route_locked) if plan_route is not None else bool(exec_route_locked)
    effective_route = (plan_route or exec_route or "").strip().lower() or None

    # Strict lock semantics: if locked to data_query, agents must include it and pattern must be data_query
    if effective_locked and effective_route == "data_query":
        if "data_query" not in norm_agents:
            raise ValueError("Locked route target 'data_query' requires 'data_query' in plan.agents")
        if pattern != "data_query":
            raise ValueError("Locked route target 'data_query' requires plan.pattern='data_query'")

    # Preserve the rest of the fields (do NOT drop them)
    skip_agents = getattr(plan, "skip_agents", None)
    if skip_agents is None:
        skip_agents = []
    if not isinstance(skip_agents, list) or not all(isinstance(a, str) for a in skip_agents):
        raise TypeError("ExecutionPlan.skip_agents must be list[str] when provided")

    resume_query = getattr(plan, "resume_query", None)
    if resume_query is not None and not isinstance(resume_query, str):
        raise TypeError("ExecutionPlan.resume_query must be str when provided")

    meta = getattr(plan, "meta", None)
    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        raise TypeError("ExecutionPlan.meta must be dict when provided")

    # Return the same plan type, with normalized fields (minimal clamping, preserve extras)
    return ExecutionPlan(
        pattern=pattern,
        agents=norm_agents,
        entry_point=entry_point,
        skip_agents=[str(a).strip().lower() for a in skip_agents if str(a).strip()],
        resume_query=resume_query.strip() if isinstance(resume_query, str) and resume_query.strip() else None,
        route=plan_route.strip().lower() if isinstance(plan_route, str) and plan_route.strip() else None,
        route_locked=bool(plan_route_locked),
        meta=dict(meta),
    )


def _wizard_collect_details_fastpath(exec_state: Dict[str, Any]) -> Optional[ExecutionPlan]:
    """
    Wizard collect-details fast-path (CRITICAL):

    If the DataQuery wizard is in progress and step == "collect_details",
    and we are NOT awaiting a pending_action confirmation,
    then we MUST NOT run refiner and MUST start at data_query.

    This MUST apply even when route_locked=True (because route_locked is not "entry_point_locked").
    """
    wizard = exec_state.get("wizard") or {}
    pending = exec_state.get("pending_action") or {}

    wizard_in_progress = bool(exec_state.get("wizard_in_progress")) or bool(wizard)
    wizard_step = wizard.get("step") if isinstance(wizard, dict) else None

    awaiting = isinstance(pending, dict) and pending.get("awaiting") is True

    if wizard_in_progress and wizard_step == "collect_details" and not awaiting:
        return ExecutionPlan(
            pattern="data_query",
            agents=["data_query", "final"],
            entry_point="data_query",
            route="data_query",
            route_locked=True,
            meta={"reason": "wizard_in_progress_collect_details_fastpath", "source": "planner"},
        )

    return None


class Planner:
    """
    STRICT Planner:

    - Only entrypoint: plan(exec_state=..., request=...) -> ExecutionPlan
    - Rules evaluated in order; first match wins.
    """

    def __init__(self, rules: List[PlanningRule]):
        if not isinstance(rules, list) or not rules:
            raise ValueError("Planner requires a non-empty list of rules")
        self.rules = rules

    def plan(self, *, exec_state: Dict[str, Any], request: Dict[str, Any]) -> ExecutionPlan:
        if not isinstance(exec_state, dict):
            raise TypeError("exec_state must be dict[str, Any]")
        if not isinstance(request, dict):
            raise TypeError("request must be dict[str, Any]")

        # ✅ 0) Wizard collect-details fast-path MUST win (even under route lock)
        wizard_fast = _wizard_collect_details_fastpath(exec_state)
        if wizard_fast is not None:
            enforced = _enforce_plan_invariants(exec_state, wizard_fast)

            logger.info(
                "planning.wizard_collect_details_fastpath",
                extra={
                    "event": "planning.wizard_collect_details_fastpath",
                    "wizard_in_progress": bool(exec_state.get("wizard_in_progress")) or bool(exec_state.get("wizard")),
                    "wizard_step": (exec_state.get("wizard") or {}).get("step") if isinstance(exec_state.get("wizard"), dict) else None,
                    "route_locked": bool(exec_state.get("route_locked")),
                    "locked_route": (exec_state.get("route") or "").strip().lower() or None,
                    "plan_pattern": getattr(enforced, "pattern", None),
                    "plan_route": getattr(enforced, "route", None),
                    "plan_agents": getattr(enforced, "agents", None),
                    "plan_entry_point": getattr(enforced, "entry_point", None),
                    "plan_meta": getattr(enforced, "meta", None),
                },
            )
            return enforced

        # ✅ 1) Honor route lock NEXT (best practice)
        if bool(exec_state.get("route_locked")):
            locked_route = (exec_state.get("route") or "").strip().lower()
            locked_pattern = (exec_state.get("graph_pattern") or "").strip().lower()

            # Keep a valid contract default if graph_pattern is absent/empty.
            if not locked_pattern:
                locked_pattern = "standard"
            if locked_pattern == "superset":
                raise ValueError(
                    "Contract Superset Mode: exec_state['graph_pattern'] must be a canonical contract pattern "
                    "('standard' | 'data_query'), not 'superset'."
                )

            # Choose agents/entry_point that satisfy invariants under the lock.
            # IMPORTANT: route lock does NOT imply "start at refiner". It only constrains the contract/pattern.
            agents: list[str] = ["refiner", "final"]
            entry_point = "refiner"

            if locked_pattern == "data_query" or locked_route == "data_query":
                agents = ["refiner", "data_query", "final"]
                entry_point = "refiner"
                locked_pattern = "data_query"

            locked_plan = ExecutionPlan(
                pattern=locked_pattern,
                agents=agents,
                entry_point=entry_point,
                route=locked_route or None,
                route_locked=True,
                meta={"reason": "route_locked", "source": "lock"},
            )

            enforced = _enforce_plan_invariants(exec_state, locked_plan)

            logger.info(
                "planning.route_locked",
                extra={
                    "event": "planning.route_locked",
                    "route_locked": True,
                    "locked_route": locked_route or None,
                    "locked_pattern": locked_pattern,
                    "plan_pattern": getattr(enforced, "pattern", None),
                    "plan_route": getattr(enforced, "route", None),
                    "plan_agents": getattr(enforced, "agents", None),
                    "plan_entry_point": getattr(enforced, "entry_point", None),
                    "plan_skip_agents": getattr(enforced, "skip_agents", None),
                    "plan_meta": getattr(enforced, "meta", None),
                },
            )
            return enforced

        # ✅ 2) Normal planning rules after this
        for rule in self.rules:
            fn = getattr(rule, "apply", None)
            if fn is None or not callable(fn):
                raise TypeError(f"Planning rule {type(rule).__name__} has no callable apply()")

            candidate = rule.apply(exec_state=exec_state, request=request)
            if candidate is not None:
                return _enforce_plan_invariants(exec_state, candidate)

        # Contract Superset Mode default:
        # choose the superset-capable contract pattern so the graph contains the DB branch.
        # ✅ Include data_query agent so downstream execution doesn't depend on implicit inclusion.
        default_plan = ExecutionPlan(
            pattern="data_query",
            agents=["refiner", "data_query", "final"],
            entry_point="refiner",
            meta={"reason": "default_contract_superset", "source": "planner"},
        )
        return _enforce_plan_invariants(exec_state, default_plan)
