from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ExecutionPlan:
    """
    Pure planning output.

    Orchestrator consumes this plan to build/invoke the graph.
    """
    agents_to_run: List[str]
    requested_agents: Optional[List[str]] = None  # caller override (if any)
    routing_decision: Optional[Any] = None  # RoutingDecision object or dict
    routing_meta: Dict[str, Any] = field(default_factory=dict)

    # knobs that affect graph build policy (cached topology)
    allow_auto_inject_nodes: bool = False

    def __post_init__(self):
        """
        Post-initialization to log details of the execution plan.
        """
        logger.debug(f"ExecutionPlan created: {self}")

        # Log detailed routing meta if available
        if self.routing_meta:
            logger.debug(f"ExecutionPlan routing meta: {self.routing_meta}")

        # Log the requested agents if they exist
        if self.requested_agents:
            logger.info(
                f"ExecutionPlan: Caller requested agents: {self.requested_agents}"
            )
        else:
            logger.info("ExecutionPlan: No caller override for agents.")

        # Log if auto-injection of nodes is allowed
        if self.allow_auto_inject_nodes:
            logger.info("ExecutionPlan: Auto-inject nodes is enabled.")
        else:
            logger.info("ExecutionPlan: Auto-inject nodes is disabled.")

        # Log the list of agents to run
        logger.info(f"ExecutionPlan: Agents to run: {self.agents_to_run}")

        # Log the routing decision if available
        if self.routing_decision:
            logger.info(
                f"ExecutionPlan: Routing decision available: {self.routing_decision}"
            )
        else:
            logger.warning("ExecutionPlan: No routing decision provided.")
