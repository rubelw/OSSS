# routing_adapter.py
from typing import Optional
from .routing_types import RoutingResult
from OSSS.ai.orchestrator.nodes.decision_node import DecisionNode
from OSSS.ai.orchestrator.nodes.base_advanced_node import NodeExecutionContext

def route_agents_with_decision_node(
    decision_node: DecisionNode,
    ctx: NodeExecutionContext,
    *,
    default_pattern: str = "standard",
    path_to_pattern: Optional[dict[str, str]] = None,
) -> RoutingResult:
    """
    Runs DecisionNode and converts its output into GraphFactory inputs.
    """
    result = ctx.loop.run_until_complete(decision_node.execute(ctx))  # or await in async caller

    agents = [a.lower() for a in (result.get("selected_agents") or [])]
    if not agents:
        # fail safe: minimal
        agents = ["refiner", "final"]

    pattern = default_pattern
    if path_to_pattern:
        pattern = path_to_pattern.get(result.get("selected_path"), default_pattern)

    return RoutingResult(
        agents=agents,
        pattern=pattern,
        meta={
            "selected_path": result.get("selected_path"),
            "confidence": result.get("confidence"),
            "reasoning": result.get("reasoning"),
        },
    )
