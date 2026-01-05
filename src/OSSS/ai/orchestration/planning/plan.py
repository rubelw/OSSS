# OSSS/ai/orchestration/planning/plan.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ExecutionPlan:
    pattern: str
    agents: List[str]
    entry_point: str
    skip_agents: List[str] = field(default_factory=list)
    resume_query: Optional[str] = None
    route: Optional[str] = None
    route_locked: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_execution_state_patch(self) -> Dict[str, Any]:
        """
        STRICT: emits only canonical Option A planning artifacts.
        No back-compat keys.
        """
        return {
            "execution_plan": {
                "pattern": self.pattern,
                "agents": list(self.agents),
                "entry_point": self.entry_point,
                "skip_agents": list(self.skip_agents),
                "resume_query": self.resume_query,
                "route": self.route,
                "route_locked": bool(self.route_locked),
                "meta": dict(self.meta),
            }
        }
