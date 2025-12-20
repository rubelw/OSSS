from typing import Callable, Dict, List, Optional
from abc import ABC, abstractmethod
import re
from OSSS.ai.context import AgentContext
from OSSS.ai.observability import get_logger

# Get logger for this module
logger = get_logger(__name__)

HISTORY_TRIGGERS = re.compile(
    r"\b(history|historical|timeline|previous|earlier|last time|recap|what happened|"
    r"prior|meeting notes|notes|minutes|decision|context|background)\b",
    re.IGNORECASE,
)

def should_run_historian(query: str) -> bool:
    q = (query or "").strip()

    # Very short queries never need historian
    if len(q) < 40:
        logger.debug("Query too short for historian: %s", q)
        return False

    # Explicit historical intent
    if HISTORY_TRIGGERS.search(q):
        logger.debug("Query matches historical intent trigger: %s", q)
        return True

    # Explicit doc usage
    ql = q.lower()
    if "notes" in ql or "docs" in ql:
        logger.debug("Query matches document intent: %s", q)
        return True

    logger.debug("Query does not match historian criteria: %s", q)
    return False

class RoutingFunction(ABC):
    """
    Abstract base class for all routing functions.

    A routing function is a callable object that:
    1. Inspects the current AgentContext
    2. Returns the *name of the next graph node* to execute
    """
    @abstractmethod
    def __call__(self, context: AgentContext) -> str:
        pass

    @abstractmethod
    def get_possible_targets(self) -> List[str]:
        pass

class ConditionalRouter(RoutingFunction):
    """
    Router that selects the next node based on ordered condition checks.
    """

    def __init__(
        self,
        conditions: List[tuple[Callable[[AgentContext], bool], str]],
        default: str,
    ) -> None:
        self.conditions = conditions
        self.default = default
        logger.debug("Initialized ConditionalRouter with %d conditions", len(conditions))

    def __call__(self, context: AgentContext) -> str:
        logger.debug("Evaluating conditions for ConditionalRouter")
        for condition_func, target_node in self.conditions:
            if condition_func(context):
                logger.debug("Condition matched, routing to node: %s", target_node)
                return target_node

        logger.debug("No conditions matched, routing to default node: %s", self.default)
        return self.default

    def get_possible_targets(self) -> List[str]:
        targets = [target for _, target in self.conditions]
        targets.append(self.default)
        logger.debug("Possible targets: %s", targets)
        return list(set(targets))


class SuccessFailureRouter(RoutingFunction):
    """
    Router that branches based on whether the last agent execution succeeded.
    """

    def __init__(self, success_target: str, failure_target: str) -> None:
        self.success_target = success_target
        self.failure_target = failure_target
        logger.debug("Initialized SuccessFailureRouter with success: %s, failure: %s", success_target, failure_target)

    def __call__(self, context: AgentContext) -> str:
        last_agent_success = context.execution_state.get("last_agent_success", True)
        logger.debug("Evaluating SuccessFailureRouter, last agent success: %s", last_agent_success)

        if last_agent_success:
            logger.debug("Routing to success target: %s", self.success_target)
            return self.success_target
        else:
            logger.debug("Routing to failure target: %s", self.failure_target)
            return self.failure_target

    def get_possible_targets(self) -> List[str]:
        return [self.success_target, self.failure_target]


class OutputBasedRouter(RoutingFunction):
    """
    Router that inspects agent output text to determine routing.
    """

    def __init__(self, output_patterns: Dict[str, str], default: str) -> None:
        self.output_patterns = output_patterns
        self.default = default
        logger.debug("Initialized OutputBasedRouter with patterns: %s", output_patterns)

    def __call__(self, context: AgentContext) -> str:
        if context.agent_outputs:
            last_agent = list(context.agent_outputs.keys())[-1]
            last_output = context.agent_outputs[last_agent]

            logger.debug("Evaluating OutputBasedRouter, last agent: %s, output: %s", last_agent, last_output)

            for pattern, target in self.output_patterns.items():
                if pattern.lower() in last_output.lower():
                    logger.debug("Pattern matched, routing to node: %s", target)
                    return target

        logger.debug("No pattern matched, routing to default node: %s", self.default)
        return self.default

    def get_possible_targets(self) -> List[str]:
        targets = list(self.output_patterns.values())
        targets.append(self.default)
        logger.debug("Possible targets for OutputBasedRouter: %s", targets)
        return list(set(targets))


class FailureHandlingRouter(RoutingFunction):
    """
    Router implementing retry logic and an optional circuit breaker.
    """

    def __init__(
        self,
        success_target: str,
        failure_target: str,
        retry_target: Optional[str] = None,
        max_failures: int = 3,
        enable_circuit_breaker: bool = True,
    ) -> None:
        self.success_target = success_target
        self.failure_target = failure_target
        self.retry_target = retry_target or failure_target
        self.max_failures = max_failures
        self.enable_circuit_breaker = enable_circuit_breaker

        self.failure_count = 0
        self.circuit_open = False
        logger.debug("Initialized FailureHandlingRouter with success: %s, failure: %s", success_target, failure_target)

    def __call__(self, context: AgentContext) -> str:
        last_agent_success = context.execution_state.get("last_agent_success", True)
        logger.debug("Evaluating FailureHandlingRouter, last agent success: %s", last_agent_success)

        if last_agent_success:
            self.failure_count = 0
            self.circuit_open = False
            logger.debug("Routing to success target: %s", self.success_target)
            return self.success_target

        self.failure_count += 1
        if self.enable_circuit_breaker and self.failure_count >= self.max_failures:
            self.circuit_open = True
            logger.warning("Circuit breaker triggered, routing to failure target: %s", self.failure_target)
            return self.failure_target

        current_retry_count = context.execution_state.get("retry_count", 0)
        if current_retry_count < self.max_failures and not self.circuit_open:
            context.execution_state["retry_count"] = current_retry_count + 1
            logger.debug("Retrying, routing to retry target: %s", self.retry_target)
            return self.retry_target

        logger.debug("Max retries reached, routing to failure target: %s", self.failure_target)
        return self.failure_target

    def get_possible_targets(self) -> List[str]:
        targets = [self.success_target, self.failure_target]
        if self.retry_target not in targets:
            targets.append(self.retry_target)
        logger.debug("Possible targets for FailureHandlingRouter: %s", targets)
        return targets


# ---------------------------------------------------------------------------
# Extended routing factory helpers
# ---------------------------------------------------------------------------

def route_with_failure_handling(
    success_target: str,
    failure_target: str,
    retry_target: Optional[str] = None,
    max_failures: int = 3,
) -> RoutingFunction:
    """
    Factory for FailureHandlingRouter.
    """
    logger.debug("Creating FailureHandlingRouter with success: %s, failure: %s", success_target, failure_target)
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
    """
    Factory for AgentDependencyRouter.
    """
    logger.debug("Creating AgentDependencyRouter with dependencies: %s", target_dependencies)
    return AgentDependencyRouter(
        dependency_map=target_dependencies,
        success_target=success_target,
        wait_target=wait_target,
        failure_target=failure_target,
    )


def route_by_pipeline_stage(
    stage_routing: Dict[str, str], default_target: str = "end"
) -> RoutingFunction:
    """
    Factory for PipelineStageRouter.
    """
    logger.debug("Creating PipelineStageRouter with stage mapping: %s", stage_routing)
    return PipelineStageRouter(stage_map=stage_routing, default_target=default_target)
