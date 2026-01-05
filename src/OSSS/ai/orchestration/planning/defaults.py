# OSSS/ai/orchestration/planning/defaults.py
from __future__ import annotations

from OSSS.ai.orchestration.planning.planner import Planner
from OSSS.ai.orchestration.planning.rules import (
    NormalizeEndRouteRule,
    WizardConfirmTableRejectRule,
    LockedRouteRule,
    DBQuerySignalsRule,
    ExplicitPatternRule,
)


def build_default_planner() -> Planner:
    """
    Contract Superset Mode (Fix 1) default planner.

    Contract:
    - Planner emits ONLY canonical contract patterns that exist in graph-patterns.json:
        "standard", "data_query"
    - "superset" is NOT a pattern name.
    - Superset behavior is expressed via compile strategy (compile_variant/agents_superset)
      and/or orchestrator compile logic, not by planner pattern output.
    - Rules are evaluated in priority order; first match wins.

    Priority rationale:
    1) NormalizeEndRouteRule: normalize route='end' -> 'final' (hard safety invariant).
    2) WizardConfirmTableRejectRule: wizard UX safety (no DB; lock to final).
    3) LockedRouteRule: if upstream already locked route (e.g., route_locked=True + route='data_query'),
       planner MUST emit a plan consistent with that lock (prevents falling through to default).
    4) DBQuerySignalsRule: if signals lock to data_query, MUST include DB agents.
    5) ExplicitPatternRule: honor caller explicit contract pattern (only if truly explicit).
    """
    return Planner(
        rules=[
            # 1) Normalize route="end" -> route="final"
            NormalizeEndRouteRule(default_pattern="data_query"),

            # 2) Wizard confirm_table "no" -> answer wizard original via non-DB path
            WizardConfirmTableRejectRule(default_pattern="data_query"),

            # 3) Upstream already locked route -> emit consistent plan (critical for orchestrator re-planning)
            LockedRouteRule(
                default_pattern="data_query",
                data_query_agents=("refiner", "data_query", "historian", "final"),
            ),

            # 4) DB signals (locked) -> route data_query WITHIN contract pattern "data_query"
            DBQuerySignalsRule(
                default_pattern="data_query",
                data_query_agents=("refiner", "data_query", "historian", "final"),
                entry_point="refiner",
            ),

            # 5) Caller explicit graph_pattern (ONLY canonical contracts; only if explicit)
            ExplicitPatternRule(
                allowed_patterns=("standard", "data_query"),
            ),
        ]
    )
