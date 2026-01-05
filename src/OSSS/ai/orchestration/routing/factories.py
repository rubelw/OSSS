"""
Router factory helpers.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from OSSS.ai.context import AgentContext
from OSSS.ai.observability import get_logger

from .interfaces import RoutingFunction
from .routers import (
    OutputBasedRouter,
    SuccessFailureRouter,
    FailureHandlingRouter,
    AgentDependencyRouter,
    PipelineStageRouter,
)

logger = get_logger(__name__)


def always_continue_to(target: str) -> RoutingFunction:
    class AlwaysRouter(RoutingFunction):
        def __call__(self, context: AgentContext) -> str:
            logger.debug(
                "AlwaysRouter routing",
                extra={"event": "router_route", "router": "AlwaysRouter", "target": target},
            )
            return target

        def get_possible_targets(self) -> List[str]:
            return [target]

    logger.debug(
        "Created AlwaysRouter via factory",
        extra={"event": "router_factory_create", "factory": "always_continue_to", "target": target},
    )
    return AlwaysRouter()


def route_on_query_type(patterns: Dict[str, str], default: str) -> RoutingFunction:
    logger.debug(
        "Creating OutputBasedRouter via route_on_query_type",
        extra={
            "event": "router_factory_create",
            "factory": "route_on_query_type",
            "pattern_count": len(patterns),
            "default_target": default,
        },
    )
    return OutputBasedRouter(patterns, default)


def route_on_success_failure(success_target: str, failure_target: str) -> RoutingFunction:
    logger.debug(
        "Creating SuccessFailureRouter via route_on_success_failure",
        extra={
            "event": "router_factory_create",
            "factory": "route_on_success_failure",
            "success_target": success_target,
            "failure_target": failure_target,
        },
    )
    return SuccessFailureRouter(success_target, failure_target)


def route_with_failure_handling(
    success_target: str,
    failure_target: str,
    retry_target: Optional[str] = None,
    max_failures: int = 3,
) -> RoutingFunction:
    logger.debug(
        "Creating FailureHandlingRouter via route_with_failure_handling",
        extra={
            "event": "router_factory_create",
            "factory": "route_with_failure_handling",
            "success_target": success_target,
            "failure_target": failure_target,
            "retry_target": retry_target or failure_target,
            "max_failures": max_failures,
        },
    )
    return FailureHandlingRouter(
        success_target=success_target,
        failure_target=failure_target,
        retry_target=retry_target,
        max_failures=max_failures,
    )


def route_with_dependencies(
    target_dependencies: Dict[str, List[str]],
    success_target: str,
    wait_target: str = "wait",
    failure_target: str = "error",
) -> RoutingFunction:
    logger.debug(
        "Creating AgentDependencyRouter via route_with_dependencies",
        extra={
            "event": "router_factory_create",
            "factory": "route_with_dependencies",
            "success_target": success_target,
            "wait_target": wait_target,
            "failure_target": failure_target,
            "dependency_keys": list(target_dependencies.keys()),
        },
    )
    return AgentDependencyRouter(
        dependency_map=target_dependencies,
        success_target=success_target,
        wait_target=wait_target,
        failure_target=failure_target,
    )


def route_by_pipeline_stage(stage_routing: Dict[str, str], default_target: str = "end") -> RoutingFunction:
    logger.debug(
        "Creating PipelineStageRouter via route_by_pipeline_stage",
        extra={
            "event": "router_factory_create",
            "factory": "route_by_pipeline_stage",
            "default_target": default_target,
            "stage_keys": list(stage_routing.keys()),
        },
    )
    return PipelineStageRouter(stage_map=stage_routing, default_target=default_target)
