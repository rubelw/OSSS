# src/OSSS/ai/orchestration/planning_bridge.py

from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, Iterable, List, Set, TYPE_CHECKING

if TYPE_CHECKING:
    # Only for type checkers; avoids runtime circular import
    from .graph_factory import GraphConfig


def _ensure_execution_config(exec_state: Dict[str, Any], logger) -> Dict[str, Any]:
    """
    Ensure exec_state["execution_config"] exists and is a dict.
    """
    ec = exec_state.get("execution_config")
    if not isinstance(ec, dict):
        logger.debug(
            "execution_config missing or not dict; initializing new dict",
            extra={"prev_type": type(ec).__name__ if ec is not None else None},
        )
        ec = {}
        exec_state["execution_config"] = ec
    else:
        logger.debug(
            "execution_config found",
            extra={"keys": list(ec.keys())},
        )
        return ec

    return ec


def apply_option_a_planning_bridge(
    cfg: "GraphConfig",
    *,
    fastpath_planner,
    prestep_agents: Iterable[str],
    logger,
) -> "GraphConfig":
    """
    Option A planning bridge (module-level):

    Decide between:
      - 'standard' pattern (conversational):
          refiner -> final -> END
      - 'data_query' pattern (DB / action / query-ish):
          refiner -> data_query -> (historian) -> END

    Rules:

    1) If DBQueryRouter has explicitly routed to data_query
       (route == 'data_query' or locked route_key == 'action'):
           -> use 'data_query'

    2) Otherwise:

       If BOTH:
         - classifier intent != "action"
         - original user text does NOT contain "query" or "database"
         - no wizard state
       THEN:
         -> use 'standard'
       ELSE:
         -> use 'data_query'

    IMPORTANT:
    - Mutates cfg.execution_state["execution_config"]["graph_pattern"]
    - Mutates cfg.execution_state["planned_agents"]
    - Returns a new GraphConfig with updated pattern_name and agents_to_run
    """
    logger.info(
        "[OptionA] Applying planning bridge",
        extra={
            "pattern_name_before": cfg.pattern_name,
            "agents_before": cfg.agents_to_run,
        },
    )

    exec_state = cfg.execution_state
    if not isinstance(exec_state, dict):
        logger.debug(
            "[OptionA] execution_state missing or not dict; skipping planning bridge",
            extra={
                "exec_state_type": type(exec_state).__name__
                if exec_state is not None
                else None,
            },
        )
        return cfg

    # Let the existing fast-path planner run for any side-effects you still want
    chosen_target = cfg.chosen_target or exec_state.get("route")
    if not isinstance(chosen_target, str):
        chosen_target = ""
    logger.debug(
        "[OptionA] Running fastpath planning",
        extra={"chosen_target": chosen_target or "refiner"},
    )
    fastpath_planner(exec_state=exec_state, chosen_target=chosen_target or "refiner")

    ec = _ensure_execution_config(exec_state, logger)

    # ------------------------------------------------------------------
    # 1) Respect DBQueryRouter route if present
    # ------------------------------------------------------------------
    route = exec_state.get("route")
    route_key_raw = exec_state.get("route_key", "")
    route_key = str(route_key_raw).strip().lower() if route_key_raw is not None else ""
    route_locked = bool(exec_state.get("route_locked"))
    route_reason = exec_state.get("route_reason")

    logger.info(
        "[OptionA] Router state before pattern decision",
        extra={
            "route": route,
            "route_key": route_key,
            "route_locked": route_locked,
            "route_reason": route_reason,
        },
    )

    if route == "data_query" or (route_key == "action" and route_locked):
        effective_pattern = "data_query"
        logger.info(
            "[OptionA] Forcing data_query pattern from DBQueryRouter",
            extra={
                "effective_pattern": effective_pattern,
                "route": route,
                "route_key": route_key,
                "route_locked": route_locked,
                "route_reason": route_reason,
            },
        )
    else:
        # ------------------------------------------------------------------
        # 2) Use classifier + lexical rule
        # ------------------------------------------------------------------
        task_cls = exec_state.get("task_classification") or {}
        classifier_intent = (task_cls.get("intent") or "").strip().lower()

        classifier_profile = exec_state.get("classifier_profile") or {}
        original_text = (
            classifier_profile.get("original_text")
            or exec_state.get("query")
            or exec_state.get("user_query")
            or exec_state.get("raw_query")
            or exec_state.get("original_query")
            or ""
        )
        original_text_str = str(original_text)
        original_lower = original_text_str.lower()

        has_query_kw = "query" in original_lower
        has_database_kw = "database" in original_lower

        wizard_state = exec_state.get("wizard")
        has_wizard = bool(wizard_state)

        # Rule:
        # If intent != "action" AND no query/database AND no wizard -> standard
        # Else -> data_query
        if (
            classifier_intent != "action"
            and not has_query_kw
            and not has_database_kw
            and not has_wizard
        ):
            effective_pattern = "standard"
        else:
            effective_pattern = "data_query"

        logger.info(
            "[OptionA] Pattern decided from classifier/keywords",
            extra={
                "effective_pattern": effective_pattern,
                "classifier_intent": classifier_intent,
                "raw_query_len": len(original_text_str),
                "raw_query_has_query": has_query_kw,
                "raw_query_has_database": has_database_kw,
                "has_wizard": has_wizard,
            },
        )

    # Persist the pattern choice into execution_config
    ec["graph_pattern"] = effective_pattern

    # ------------------------------------------------------------------
    # 3) Normalize planned_agents to match pattern
    # ------------------------------------------------------------------
    prestep_set: Set[str] = {str(a).lower() for a in prestep_agents or []}

    planned_from_state = exec_state.get("planned_agents")
    if isinstance(planned_from_state, list) and planned_from_state:
        # ✅ Respect precomputed planned_agents from execution_state as
        #    authoritative about which nodes should exist. We only:
        #      - lower-case
        #      - drop duplicates
        #      - strip prestep agents (e.g. 'classifier')
        normalized: List[str] = []
        seen: Set[str] = set()
        for a in planned_from_state:
            if not a:
                continue
            s = str(a).lower()
            if s in prestep_set:
                continue
            if s not in seen:
                seen.add(s)
                normalized.append(s)

        exec_state["planned_agents"] = normalized

        logger.info(
            "[OptionA] Using existing planned_agents from execution_state",
            extra={
                "effective_pattern": effective_pattern,
                "planned_agents": normalized,
            },
        )

        # Keep cfg agents in sync but do NOT auto-inject 'refiner' here.
        return replace(
            cfg,
            pattern_name=effective_pattern,
            agents_to_run=normalized,
        )

    # No state-level plan yet: fall back to automatic planning from cfg.agents_to_run
    base_planned = [str(a).lower() for a in (cfg.agents_to_run or []) if a]
    normalized: List[str] = [a for a in base_planned if a]

    # For auto-planned flows, still ensure refiner is present
    if "refiner" not in normalized:
        normalized.insert(0, "refiner")

    if effective_pattern == "standard":
        # refiner -> final -> END
        normalized = [
            a
            for a in normalized
            if a not in {"data_query", "historian", "critic", "synthesis"}
        ]
        if "final" not in normalized:
            normalized.append("final")
    else:
        # data_query-style:
        #   refiner -> data_query -> (historian) -> END
        normalized = [
            a for a in normalized if a not in {"final", "synthesis", "critic"}
        ]
        if "data_query" not in normalized:
            normalized.append("data_query")

    # Stable de-dupe
    deduped: List[str] = []
    seen: Set[str] = set()
    for a in normalized:
        if a not in seen:
            seen.add(a)
            deduped.append(a)

    exec_state["planned_agents"] = deduped

    logger.info(
        "[OptionA] Planned agents normalized",
        extra={
            "effective_pattern": effective_pattern,
            "planned_agents": deduped,
        },
    )

    # Override cfg with our effective pattern + planned agents
    cfg = replace(
        cfg,
        pattern_name=effective_pattern,
        agents_to_run=deduped,
    )

    logger.info(
        "[OptionA] Planning bridge complete",
        extra={
            "pattern_name_after": cfg.pattern_name,
            "agents_after": cfg.agents_to_run,
        },
    )
    return cfg
