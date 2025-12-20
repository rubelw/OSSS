# OSSS/ai/planning/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ExecutionPlan:
    """
    Pure planning output.

    Orchestrator consumes this plan to build/invoke the graph.
    """
    agents_to_run: List[str]
    requested_agents: Optional[List[str]] = None  # caller override (if any)
    routing_decision: Optional[Any] = None        # RoutingDecision object or dict
    routing_meta: Dict[str, Any] = field(default_factory=dict)

    # knobs that affect graph build policy (cached topology)
    allow_auto_inject_nodes: bool = False
