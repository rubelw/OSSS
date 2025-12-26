# routing_adapter.py
from typing import Optional

from .routing_types import RoutingResult
from OSSS.ai.orchestrator.nodes.decision_node import DecisionNode
from OSSS.ai.orchestrator.nodes.base_advanced_node import NodeExecutionContext
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)


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
    logger.debug(
        "Starting route_agents_with_decision_node",
        extra={
            "event": "routing_adapter_start",
            "decision_node": getattr(decision_node, "name", None),
            "default_pattern": default_pattern,
            "has_path_to_pattern": bool(path_to_pattern),
            "execution_state_keys": list(getattr(ctx, "execution_state", {}).keys())
            if getattr(ctx, "execution_state", None)
            else [],
        },
    )

    try:
        # NOTE: Orchestrator owns the loop; this is the sync entry point.
        result = ctx.loop.run_until_complete(decision_node.execute(ctx))  # or await in async caller

        logger.debug(
            "DecisionNode execution completed",
            extra={
                "event": "routing_adapter_decision_node_complete",
                "decision_node": getattr(decision_node, "name", None),
                "raw_result_keys": list(result.keys()) if isinstance(result, dict) else None,
                "selected_path": result.get("selected_path") if isinstance(result, dict) else None,
                "confidence": result.get("confidence") if isinstance(result, dict) else None,
            },
        )
    except Exception as exc:
        logger.error(
            "Error executing DecisionNode in route_agents_with_decision_node",
            exc_info=True,
            extra={
                "event": "routing_adapter_error",
                "decision_node": getattr(decision_node, "name", None),
                "error_type": type(exc).__name__,
            },
        )
        # Hard fallback: return minimal safe routing result
        fallback = RoutingResult(
            agents=["refiner", "final"],
            pattern=default_pattern,
            meta={
                "error": str(exc),
                "decision_node": getattr(decision_node, "name", None),
                "fallback_reason": "decision_node_execution_error",
            },
        )
        logger.debug(
            "Returning fallback RoutingResult after error",
            extra={
                "event": "routing_adapter_fallback",
                "agents": fallback.agents,
                "pattern": fallback.pattern,
            },
        )
        return fallback

    # Normal path: parse DecisionNode result
    if not isinstance(result, dict):
        logger.warning(
            "DecisionNode returned non-dict result; using fallback agents/pattern",
            extra={
                "event": "routing_adapter_non_dict_result",
                "decision_node": getattr(decision_node, "name", None),
                "result_type": type(result).__name__,
            },
        )
        result = {}

    agents = [a.lower() for a in (result.get("selected_agents") or [])]
    if not agents:
        logger.warning(
            "DecisionNode returned no selected_agents; using fallback ['refiner', 'final']",
            extra={
                "event": "routing_adapter_no_agents",
                "decision_node": getattr(decision_node, "name", None),
            },
        )
        agents = ["refiner", "final"]

    pattern = default_pattern
    selected_path = result.get("selected_path")

    if path_to_pattern:
        mapped_pattern = path_to_pattern.get(selected_path)
        if mapped_pattern:
            pattern = mapped_pattern
            logger.debug(
                "Mapped selected_path to pattern via path_to_pattern",
                extra={
                    "event": "routing_adapter_pattern_mapped",
                    "decision_node": getattr(decision_node, "name", None),
                    "selected_path": selected_path,
                    "mapped_pattern": mapped_pattern,
                },
            )
        else:
            logger.debug(
                "No pattern mapping found for selected_path; using default",
                extra={
                    "event": "routing_adapter_pattern_defaulted",
                    "decision_node": getattr(decision_node, "name", None),
                    "selected_path": selected_path,
                    "default_pattern": default_pattern,
                },
            )
    else:
        logger.debug(
            "No path_to_pattern provided; using default pattern",
            extra={
                "event": "routing_adapter_no_mapping_dict",
                "decision_node": getattr(decision_node, "name", None),
                "default_pattern": default_pattern,
            },
        )

    routing_result = RoutingResult(
        agents=agents,
        pattern=pattern,
        meta={
            "selected_path": selected_path,
            "confidence": result.get("confidence"),
            "reasoning": result.get("reasoning"),
        },
    )

    logger.debug(
        "route_agents_with_decision_node returning RoutingResult",
        extra={
            "event": "routing_adapter_complete",
            "decision_node": getattr(decision_node, "name", None),
            "agents": routing_result.agents,
            "pattern": routing_result.pattern,
            "selected_path": routing_result.meta.get("selected_path"),
            "confidence": routing_result.meta.get("confidence"),
        },
    )

    return routing_result
