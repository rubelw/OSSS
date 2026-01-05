# OSSS/ai/orchestration/planning/apply.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from OSSS.ai.api.models import WorkflowRequest


@dataclass(frozen=True)
class AppliedPlan:
    pattern: str
    agents: List[str]
    entry_point: str
    skip_agents: List[str]
    resume_query: Optional[str]
    route: Optional[str]
    route_locked: bool


def apply_execution_plan(
    *,
    plan: Any,  # OSSS.ai.orchestration.planning.plan.ExecutionPlan (canonical)
    request: "WorkflowRequest",
    config: Dict[str, Any],
    execution_state: Dict[str, Any],
) -> AppliedPlan:
    if not isinstance(config, dict):
        raise TypeError("config must be dict[str, Any]")
    if not isinstance(execution_state, dict):
        raise TypeError("execution_state must be dict[str, Any]")

    # ------------------------------------------------------------------
    # ✅ PATCH (3): preserve route lock (defensive hygiene)
    #
    # If the normalizer (or prior step) locked the route, we refuse to let
    # planning/apply clobber route/pattern. We still:
    #   - record the plan artifact (for observability)
    #   - apply only safe fields (agents/entry/skip/resume/etc.) to config
    #   - reassert locked graph_pattern/route into config + exec_state
    # ------------------------------------------------------------------
    locked_by_state = bool(execution_state.get("route_locked"))

    pattern = getattr(plan, "pattern", None)
    agents = getattr(plan, "agents", None)
    entry_point = getattr(plan, "entry_point", None)
    skip_agents = getattr(plan, "skip_agents", None)
    resume_query = getattr(plan, "resume_query", None)
    route = getattr(plan, "route", None)
    route_locked = getattr(plan, "route_locked", None)
    meta = getattr(plan, "meta", None)

    if not isinstance(pattern, str) or not pattern.strip():
        raise TypeError("ExecutionPlan.pattern must be a non-empty str")
    pattern_norm = pattern.strip().lower()

    if not isinstance(agents, list) or not agents:
        raise TypeError("ExecutionPlan.agents must be a non-empty list[str]")

    # normalize + de-dupe
    norm_agents: List[str] = []
    seen: set[str] = set()
    for a in agents:
        if not isinstance(a, str) or not a.strip():
            raise TypeError("ExecutionPlan.agents must contain only non-empty str")
        s = a.strip().lower()
        if s not in seen:
            seen.add(s)
            norm_agents.append(s)

    if not isinstance(entry_point, str) or not entry_point.strip():
        raise TypeError("ExecutionPlan.entry_point must be a non-empty str")
    entry_norm = entry_point.strip().lower()
    if entry_norm not in norm_agents:
        raise ValueError("ExecutionPlan.entry_point must be present in ExecutionPlan.agents")

    if skip_agents is None:
        skip_norm: List[str] = []
    else:
        if not isinstance(skip_agents, list):
            raise TypeError("ExecutionPlan.skip_agents must be list[str]")
        skip_norm = []
        seen_skip: set[str] = set()
        for a in skip_agents:
            if not isinstance(a, str) or not a.strip():
                raise TypeError("ExecutionPlan.skip_agents must contain only non-empty str")
            s = a.strip().lower()
            if s not in seen_skip:
                seen_skip.add(s)
                skip_norm.append(s)

    if resume_query is not None and (not isinstance(resume_query, str) or not resume_query.strip()):
        raise TypeError("ExecutionPlan.resume_query must be None or non-empty str")
    resume_norm = resume_query.strip() if isinstance(resume_query, str) else None

    if route is not None and (not isinstance(route, str) or not route.strip()):
        raise TypeError("ExecutionPlan.route must be None or non-empty str")
    route_norm = route.strip().lower() if isinstance(route, str) else None

    if not isinstance(route_locked, bool):
        raise TypeError("ExecutionPlan.route_locked must be bool")
    if route_locked and not route_norm:
        raise ValueError("ExecutionPlan.route_locked=True requires ExecutionPlan.route to be set")

    if meta is not None and not isinstance(meta, dict):
        raise TypeError("ExecutionPlan.meta must be dict[str, Any]")

    # --- authoritative artifact (always record what planning produced) ---
    execution_state["execution_plan"] = {
        "pattern": pattern_norm,
        "agents": list(norm_agents),
        "entry_point": entry_norm,
        "skip_agents": list(skip_norm),
        "resume_query": resume_norm,
        "route": route_norm,
        "route_locked": bool(route_locked),
        "meta": dict(meta) if isinstance(meta, dict) else {},
        "apply": {"preserved_state_lock": bool(locked_by_state)},
    }

    # ------------------------------------------------------------------
    # ✅ If exec_state locked the route, preserve graph_pattern/route from state.
    # ------------------------------------------------------------------
    if locked_by_state:
        locked_pattern = execution_state.get("graph_pattern", config.get("graph_pattern"))
        locked_route = execution_state.get("route", config.get("route"))

        # Reassert the lock into config + exec_state
        if isinstance(locked_pattern, str) and locked_pattern.strip():
            execution_state["graph_pattern"] = locked_pattern.strip().lower()
            config["graph_pattern"] = locked_pattern.strip().lower()

        if isinstance(locked_route, str) and locked_route.strip():
            execution_state["route"] = locked_route.strip().lower()
            config["route"] = locked_route.strip().lower()

        execution_state["route_locked"] = True
        config["route_locked"] = True

        # Keep execution_config in sync
        exec_cfg = execution_state.get("execution_config")
        if exec_cfg is None:
            exec_cfg = {}
            execution_state["execution_config"] = exec_cfg
        if not isinstance(exec_cfg, dict):
            raise TypeError("execution_state['execution_config'] must be dict when present")

        if isinstance(execution_state.get("graph_pattern"), str):
            exec_cfg["graph_pattern"] = execution_state["graph_pattern"]
        if isinstance(execution_state.get("entry_point"), str):
            exec_cfg["entry_point"] = execution_state["entry_point"]

        # Apply only *safe* fields that do not override locked routing.
        # (Agents/entry/skip/resume are OK; route/pattern are NOT.)
        execution_state["planned_agents"] = list(norm_agents)
        execution_state["entry_point"] = entry_norm
        execution_state["skip_agents"] = list(skip_norm)
        if resume_norm is not None:
            execution_state["resume_query"] = resume_norm

        config["agents"] = list(norm_agents)
        config["entry_point"] = entry_norm
        config["skip_agents"] = list(skip_norm)
        if resume_norm is not None:
            config["resume_query"] = resume_norm

        # Ensure the orchestrator sees the latest state
        config["execution_state"] = execution_state

        # request mutation (API-level): still safe
        request.agents = list(norm_agents)

        return AppliedPlan(
            pattern=str(execution_state.get("graph_pattern") or pattern_norm),
            agents=list(norm_agents),
            entry_point=entry_norm,
            skip_agents=list(skip_norm),
            resume_query=resume_norm,
            route=(str(execution_state.get("route") or route_norm) if (execution_state.get("route") or route_norm) else None),
            route_locked=True,
        )

    # ------------------------------------------------------------------
    # Normal (unlocked) apply: plan remains authoritative for route/pattern.
    # ------------------------------------------------------------------

    # runtime convenience keys (still strict; not “legacy guessing”)
    execution_state["planned_agents"] = list(norm_agents)
    execution_state["graph_pattern"] = pattern_norm
    execution_state["entry_point"] = entry_norm
    execution_state["skip_agents"] = list(skip_norm)
    if resume_norm is not None:
        execution_state["resume_query"] = resume_norm
    if route_norm is not None:
        execution_state["route"] = route_norm
    execution_state["route_locked"] = bool(route_locked)

    exec_cfg = execution_state.get("execution_config")
    if exec_cfg is None:
        exec_cfg = {}
        execution_state["execution_config"] = exec_cfg
    if not isinstance(exec_cfg, dict):
        raise TypeError("execution_state['execution_config'] must be dict when present")
    exec_cfg["graph_pattern"] = pattern_norm
    exec_cfg["entry_point"] = entry_norm

    # config passed into orchestrator.run()
    config["graph_pattern"] = pattern_norm
    config["agents"] = list(norm_agents)
    config["entry_point"] = entry_norm
    config["skip_agents"] = list(skip_norm)
    if resume_norm is not None:
        config["resume_query"] = resume_norm
    if route_norm is not None:
        config["route"] = route_norm
    config["route_locked"] = bool(route_locked)
    config["execution_state"] = execution_state

    # request mutation (API-level)
    request.agents = list(norm_agents)

    return AppliedPlan(
        pattern=pattern_norm,
        agents=list(norm_agents),
        entry_point=entry_norm,
        skip_agents=list(skip_norm),
        resume_query=resume_norm,
        route=route_norm,
        route_locked=bool(route_locked),
    )
