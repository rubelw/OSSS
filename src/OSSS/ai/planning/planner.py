# OSSS/ai/planning/planner.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from OSSS.ai.observability import get_logger
from OSSS.ai.langgraph_backend.graph_patterns.conditional import (
    ContextAnalyzer,
    PerformanceTracker,
)
from OSSS.ai.routing import (
    ResourceOptimizer,
    ResourceConstraints,
    OptimizationStrategy,
    RoutingDecision,
)

from .models import ExecutionPlan

logger = get_logger(__name__)


# Keep normalization rules in ONE place (matches GraphFactory normalize intent)
def _normalize_agent_name(name: str) -> str:
    n = (name or "").strip().lower()
    return {
        "data_view": "data_views",
        "data_views": "data_views",
    }.get(n, n)


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _parse_requested_agents(config: Dict[str, Any]) -> Optional[List[str]]:
    """
    Caller override: config["agents"] = ["guard", "data_views", ...]
    Returns normalized list or None.
    """
    requested = config.get("agents")
    if not isinstance(requested, list):
        return None

    out: List[str] = []
    for a in requested:
        if isinstance(a, str):
            n = _normalize_agent_name(a)
            if n:
                out.append(n)

    out = _dedupe_preserve_order(out)
    return out or None


async def _make_routing_decision(
    *,
    query: str,
    available_agents: List[str],
    config: Dict[str, Any],
    optimization_strategy: OptimizationStrategy,
    resource_optimizer: ResourceOptimizer,
    context_analyzer: ContextAnalyzer,
    performance_tracker: Optional[PerformanceTracker] = None,
) -> RoutingDecision:
    """
    The old LangGraphOrchestrator._make_routing_decision moved here.
    """
    context_analysis = context_analyzer.analyze_context(query)

    performance_data: Dict[str, Dict[str, float]] = {}
    for agent in available_agents:
        agent_lower = agent.lower()
        if performance_tracker:
            performance_data[agent_lower] = {
                "success_rate": performance_tracker.get_success_rate(agent_lower) or 0.8,
                "average_time_ms": performance_tracker.get_average_time(agent_lower) or 2000.0,
                "performance_score": performance_tracker.get_performance_score(agent_lower) or 0.7,
            }
        else:
            performance_data[agent_lower] = {
                "success_rate": 0.8,
                "average_time_ms": 2000.0,
                "performance_score": 0.7,
            }

    constraints = ResourceConstraints(
        max_execution_time_ms=config.get("max_execution_time_ms"),
        max_agents=config.get("max_agents", 4),
        min_agents=config.get("min_agents", 1),
        min_success_rate=config.get("min_success_rate", 0.7),
    )

    context_requirements = {
        "requires_research": context_analysis.requires_research,
        "requires_criticism": context_analysis.requires_criticism,
        "requires_synthesis": True,
        "requires_refinement": True,
    }

    return resource_optimizer.select_optimal_agents(
        available_agents=available_agents,
        complexity_score=context_analysis.complexity_score,
        performance_data=performance_data,
        constraints=constraints,
        strategy=optimization_strategy,
        context_requirements=context_requirements,
    )


async def build_execution_plan(
    *,
    query: str,
    config: Dict[str, Any],
    default_agents: List[str],
    use_enhanced_routing: bool,
    optimization_strategy: OptimizationStrategy,
    resource_optimizer: Optional[ResourceOptimizer],
    context_analyzer: Optional[ContextAnalyzer],
    performance_tracker: Optional[PerformanceTracker],
) -> ExecutionPlan:
    """
    Decide the plan (agent list + routing decision metadata).

    Rules:
    - If caller provides config["agents"], honor it (guard already ran outside DAG).
    - Else if enhanced routing enabled, compute routing_decision and pick selected_agents.
    - Else use default_agents.
    """
    config = config or {}

    # Normalize + dedupe defaults too (prevents topology/cache churn)
    normalized_defaults = _dedupe_preserve_order(
        [_normalize_agent_name(a) for a in (default_agents or []) if isinstance(a, str)]
    )
    normalized_defaults = [a for a in normalized_defaults if a]  # drop empty

    requested_agents = _parse_requested_agents(config)

    allow_auto_inject_nodes = bool(config.get("allow_auto_inject_nodes", False))

    # Caller override wins
    if requested_agents:
        logger.info(
            "Execution plan: caller requested agents",
            extra={"agents": requested_agents},
        )
        return ExecutionPlan(
            agents_to_run=requested_agents,
            requested_agents=requested_agents,
            routing_decision=None,
            routing_meta={"source": "caller"},
            allow_auto_inject_nodes=allow_auto_inject_nodes,
        )

    # Enhanced routing (only when no override)
    if use_enhanced_routing:
        if not (resource_optimizer and context_analyzer):
            logger.warning(
                "Enhanced routing enabled but routing components missing; falling back to defaults"
            )
            return ExecutionPlan(
                agents_to_run=list(normalized_defaults),
                requested_agents=None,
                routing_decision=None,
                routing_meta={
                    "source": "fallback_defaults",
                    "reason": "missing_routing_components",
                },
                allow_auto_inject_nodes=allow_auto_inject_nodes,
            )

        routing_decision = await _make_routing_decision(
            query=query,
            available_agents=list(normalized_defaults),
            config=config,
            optimization_strategy=optimization_strategy,
            resource_optimizer=resource_optimizer,
            context_analyzer=context_analyzer,
            performance_tracker=performance_tracker,
        )

        selected_raw = list(getattr(routing_decision, "selected_agents", []) or [])
        selected = _dedupe_preserve_order(
            [_normalize_agent_name(a) for a in selected_raw if isinstance(a, str)]
        )
        selected = [a for a in selected if a]

        if not selected:
            selected = list(normalized_defaults)

        logger.info(
            "Execution plan: enhanced routing selected agents",
            extra={
                "selected_agents": selected,
                "routing_strategy": getattr(routing_decision, "routing_strategy", None),
                "confidence": getattr(routing_decision, "confidence_score", None),
            },
        )

        return ExecutionPlan(
            agents_to_run=selected,
            requested_agents=None,
            routing_decision=routing_decision,
            routing_meta={
                "source": "enhanced_routing",
                "routing_strategy": getattr(routing_decision, "routing_strategy", None),
                "confidence_score": getattr(routing_decision, "confidence_score", None),
            },
            allow_auto_inject_nodes=allow_auto_inject_nodes,
        )

    # Defaults
    logger.info("Execution plan: defaults", extra={"agents": normalized_defaults})
    return ExecutionPlan(
        agents_to_run=list(normalized_defaults),
        requested_agents=None,
        routing_decision=None,
        routing_meta={"source": "defaults"},
        allow_auto_inject_nodes=allow_auto_inject_nodes,
    )
