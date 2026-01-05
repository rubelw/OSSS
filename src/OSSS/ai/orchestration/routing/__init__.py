"""
Routing utilities for LangGraph conditional execution.

Package split of the original routing.py to avoid module/package name collisions.
"""

from .interfaces import RoutingFunction
from .routers import (
    DBQueryRouter,
    ConditionalRouter,
    SuccessFailureRouter,
    OutputBasedRouter,
    FailureHandlingRouter,
    AgentDependencyRouter,
    PipelineStageRouter,
)
from .factories import (
    always_continue_to,
    route_on_query_type,
    route_on_success_failure,
    route_with_failure_handling,
    route_with_dependencies,
    route_by_pipeline_stage,
)
from .route_keys import planned_agents_for_route_key
from .heuristics import should_route_to_data_query, should_run_historian
from .apply import apply_db_query_routing

__all__ = [
    "RoutingFunction",
    "DBQueryRouter",
    "ConditionalRouter",
    "SuccessFailureRouter",
    "OutputBasedRouter",
    "FailureHandlingRouter",
    "AgentDependencyRouter",
    "PipelineStageRouter",
    "always_continue_to",
    "route_on_query_type",
    "route_on_success_failure",
    "route_with_failure_handling",
    "route_with_dependencies",
    "route_by_pipeline_stage",
    "planned_agents_for_route_key",
    "should_route_to_data_query",
    "apply_db_query_routing",
    "should_run_historian",
]
