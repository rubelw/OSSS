"""
Route-key → planned agent list mapping.
"""

from __future__ import annotations

from typing import List

from OSSS.ai.observability import get_logger

from .constants import ACTION_PLAN, ANALYSIS_PLAN

logger = get_logger(__name__)


def planned_agents_for_route_key(route_key: str) -> List[str]:
    k = (route_key or "").strip().lower()

    if k == "action":
        plan = ACTION_PLAN
    elif k in {"informational", "analysis", "read"}:
        plan = ANALYSIS_PLAN
    else:
        plan = ANALYSIS_PLAN

    # Safety: ensure final is always present
    if "final" not in plan:
        plan = [*plan, "final"]

    logger.debug(
        "Planned agents for route key",
        extra={"event": "routing_planned_agents", "route_key": k, "planned_agents": plan},
    )
    return plan
