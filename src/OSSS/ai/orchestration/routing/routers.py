"""
Concrete router implementations.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from OSSS.ai.context import AgentContext
from OSSS.ai.observability import get_logger

from .apply import apply_db_query_routing
from .interfaces import RoutingFunction

logger = get_logger(__name__)


class DBQueryRouter(RoutingFunction):
    def __init__(self, data_query_target: str, default_target: str) -> None:
        self.data_query_target = data_query_target
        self.default_target = default_target

        logger.debug(
            "Initialized DBQueryRouter",
            extra={
                "event": "router_init",
                "router": "DBQueryRouter",
                "data_query_target": data_query_target,
                "default_target": default_target,
            },
        )

    def __call__(self, context: AgentContext) -> str:
        try:
            if context.execution_state.get("route_locked"):
                locked_route = context.execution_state.get("route")

                if not isinstance(locked_route, str) or not locked_route.strip():
                    locked_route = self.default_target

                locked_route = locked_route.strip()
                if locked_route.lower() == "end":
                    locked_route = self.default_target

                context.execution_state["route"] = locked_route
                context.execution_state["route_locked"] = True

                context.execution_state.setdefault("entry_target", locked_route)
                context.execution_state.setdefault("entry_locked", True)
                context.execution_state.setdefault("entry_reason", "honor_route_locked")

                existing_key = context.execution_state.get("route_key")
                existing_key_s = str(existing_key).strip().lower() if existing_key is not None else ""

                known_keys = {"action", "informational", "analysis", "read"}
                if existing_key_s not in known_keys:
                    normalized_key = "action" if locked_route == self.data_query_target else "informational"
                    context.execution_state["route_key"] = normalized_key
                else:
                    context.execution_state["route_key"] = existing_key_s

                context.execution_state.setdefault("route_reason", "honor_route_locked")

                logger.debug(
                    "DBQueryRouter honoring locked route",
                    extra={
                        "event": "router_route",
                        "router": "DBQueryRouter",
                        "route_locked": True,
                        "target": locked_route,
                        "execution_state_route": context.execution_state.get("route"),
                        "execution_state_route_key": context.execution_state.get("route_key"),
                        "execution_state_route_reason": context.execution_state.get("route_reason"),
                        "execution_state_entry_target": context.execution_state.get("entry_target"),
                        "execution_state_entry_locked": context.execution_state.get("entry_locked"),
                        "execution_state_entry_reason": context.execution_state.get("entry_reason"),
                    },
                )
                return locked_route

            query = (context.query or "").strip()

            apply_db_query_routing(context.execution_state, query)

            if context.execution_state.get("route_locked"):
                target = context.execution_state.get("route") or self.default_target
                target = str(target).strip() or self.default_target

                if target == self.data_query_target:
                    context.execution_state.setdefault("route_key", "action")
                else:
                    context.execution_state.setdefault("route_key", "informational")

                logger.debug(
                    "DBQueryRouter routing via apply_db_query_routing",
                    extra={
                        "event": "router_route",
                        "router": "DBQueryRouter",
                        "target": target,
                        "route_locked": True,
                        "route_key": context.execution_state.get("route_key"),
                        "route_reason": context.execution_state.get("route_reason"),
                        "entry_target": context.execution_state.get("entry_target"),
                        "entry_locked": context.execution_state.get("entry_locked"),
                        "entry_reason": context.execution_state.get("entry_reason"),
                        "sample_query": query[:256],
                    },
                )
                return target

            context.execution_state["route"] = self.default_target
            context.execution_state["route_locked"] = False
            context.execution_state["route_key"] = "informational"
            context.execution_state["route_reason"] = "default"

            context.execution_state.setdefault("entry_target", self.default_target)
            context.execution_state.setdefault("entry_locked", False)
            context.execution_state.setdefault("entry_reason", "default")

            logger.debug(
                "DBQueryRouter routing to default target",
                extra={
                    "event": "router_route",
                    "router": "DBQueryRouter",
                    "target": self.default_target,
                    "route_locked": False,
                    "route_key": "informational",
                    "route_reason": "default",
                    "entry_target": context.execution_state.get("entry_target"),
                    "entry_locked": context.execution_state.get("entry_locked"),
                    "entry_reason": context.execution_state.get("entry_reason"),
                    "sample_query": query[:256],
                },
            )
            return self.default_target

        except Exception as exc:
            logger.error(
                "Error in DBQueryRouter",
                exc_info=True,
                extra={"event": "router_error", "router": "DBQueryRouter", "error_type": type(exc).__name__},
            )
            return self.default_target

    def get_possible_targets(self) -> List[str]:
        return [self.data_query_target, self.default_target]


class ConditionalRouter(RoutingFunction):
    def __init__(
        self,
        conditions: List[tuple[Callable[[AgentContext], bool], str]],
        default: str,
    ) -> None:
        self.conditions = conditions
        self.default = default

        logger.debug(
            "Initialized ConditionalRouter",
            extra={
                "event": "router_init",
                "router": "ConditionalRouter",
                "condition_count": len(conditions),
                "default_target": default,
            },
        )

    def __call__(self, context: AgentContext) -> str:
        try:
            for idx, (condition_func, target_node) in enumerate(self.conditions):
                try:
                    if condition_func(context):
                        logger.debug(
                            "ConditionalRouter matched condition",
                            extra={
                                "event": "router_route",
                                "router": "ConditionalRouter",
                                "condition_index": idx,
                                "target": target_node,
                            },
                        )
                        return target_node
                except Exception as exc:
                    logger.error(
                        "Error evaluating ConditionalRouter condition",
                        exc_info=True,
                        extra={
                            "event": "router_condition_error",
                            "router": "ConditionalRouter",
                            "condition_index": idx,
                            "error_type": type(exc).__name__,
                        },
                    )
                    continue

            logger.debug(
                "ConditionalRouter using default target",
                extra={"event": "router_route", "router": "ConditionalRouter", "target": self.default},
            )
            return self.default

        except Exception as exc:
            logger.error(
                "Error in ConditionalRouter",
                exc_info=True,
                extra={"event": "router_error", "router": "ConditionalRouter", "error_type": type(exc).__name__},
            )
            return self.default

    def get_possible_targets(self) -> List[str]:
        targets = [target for _, target in self.conditions]
        targets.append(self.default)
        unique_targets = list(set(targets))

        logger.debug(
            "ConditionalRouter possible targets",
            extra={"event": "router_possible_targets", "router": "ConditionalRouter", "targets": unique_targets},
        )
        return unique_targets


class SuccessFailureRouter(RoutingFunction):
    def __init__(self, success_target: str, failure_target: str) -> None:
        self.success_target = success_target
        self.failure_target = failure_target

        logger.debug(
            "Initialized SuccessFailureRouter",
            extra={
                "event": "router_init",
                "router": "SuccessFailureRouter",
                "success_target": success_target,
                "failure_target": failure_target,
            },
        )

    def __call__(self, context: AgentContext) -> str:
        try:
            success = context.execution_state.get("last_agent_success", True)
            target = self.success_target if success else self.failure_target

            logger.debug(
                "SuccessFailureRouter routing decision",
                extra={
                    "event": "router_route",
                    "router": "SuccessFailureRouter",
                    "last_agent_success": success,
                    "target": target,
                },
            )
            return target
        except Exception as exc:
            logger.error(
                "Error in SuccessFailureRouter",
                exc_info=True,
                extra={"event": "router_error", "router": "SuccessFailureRouter", "error_type": type(exc).__name__},
            )
            return self.failure_target

    def get_possible_targets(self) -> List[str]:
        return [self.success_target, self.failure_target]


class OutputBasedRouter(RoutingFunction):
    def __init__(self, output_patterns: Dict[str, str], default: str) -> None:
        self.output_patterns = output_patterns
        self.default = default

        logger.debug(
            "Initialized OutputBasedRouter",
            extra={
                "event": "router_init",
                "router": "OutputBasedRouter",
                "pattern_count": len(output_patterns),
                "default_target": default,
            },
        )

    def __call__(self, context: AgentContext) -> str:
        try:
            if context.agent_outputs:
                last_agent = list(context.agent_outputs.keys())[-1]
                last_output = context.agent_outputs[last_agent] or ""
                lowered = last_output.lower()

                for pattern, target in self.output_patterns.items():
                    if pattern.lower() in lowered:
                        logger.debug(
                            "OutputBasedRouter matched pattern",
                            extra={
                                "event": "router_route",
                                "router": "OutputBasedRouter",
                                "last_agent": last_agent,
                                "pattern": pattern,
                                "target": target,
                            },
                        )
                        return target

            logger.debug(
                "OutputBasedRouter using default target",
                extra={
                    "event": "router_route",
                    "router": "OutputBasedRouter",
                    "target": self.default,
                    "has_agent_outputs": bool(context.agent_outputs),
                },
            )
            return self.default

        except Exception as exc:
            logger.error(
                "Error in OutputBasedRouter",
                exc_info=True,
                extra={"event": "router_error", "router": "OutputBasedRouter", "error_type": type(exc).__name__},
            )
            return self.default

    def get_possible_targets(self) -> List[str]:
        targets = list(self.output_patterns.values())
        targets.append(self.default)
        return list(set(targets))


class FailureHandlingRouter(RoutingFunction):
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

        logger.debug(
            "Initialized FailureHandlingRouter",
            extra={
                "event": "router_init",
                "router": "FailureHandlingRouter",
                "success_target": success_target,
                "failure_target": failure_target,
                "retry_target": self.retry_target,
                "max_failures": max_failures,
                "enable_circuit_breaker": enable_circuit_breaker,
            },
        )

    def __call__(self, context: AgentContext) -> str:
        try:
            last_agent_success = context.execution_state.get("last_agent_success", True)

            if last_agent_success:
                self.failure_count = 0
                self.circuit_open = False
                return self.success_target

            self.failure_count += 1

            if self.enable_circuit_breaker and self.failure_count >= self.max_failures:
                self.circuit_open = True
                return self.failure_target

            current_retry_count = context.execution_state.get("retry_count", 0)
            if current_retry_count < self.max_failures and not self.circuit_open:
                context.execution_state["retry_count"] = current_retry_count + 1
                return self.retry_target

            return self.failure_target

        except Exception:
            return self.failure_target

    def get_possible_targets(self) -> List[str]:
        targets = [self.success_target, self.failure_target]
        if self.retry_target not in targets:
            targets.append(self.retry_target)
        return list(set(targets))

    def reset_failure_state(self) -> None:
        self.failure_count = 0
        self.circuit_open = False


class AgentDependencyRouter(RoutingFunction):
    def __init__(
        self,
        dependency_map: Dict[str, List[str]],
        success_target: str,
        wait_target: str,
        failure_target: str,
    ) -> None:
        self.dependency_map = dependency_map
        self.success_target = success_target
        self.wait_target = wait_target
        self.failure_target = failure_target

        logger.debug(
            "Initialized AgentDependencyRouter",
            extra={
                "event": "router_init",
                "router": "AgentDependencyRouter",
                "success_target": success_target,
                "wait_target": wait_target,
                "failure_target": failure_target,
                "dependency_keys": list(dependency_map.keys()),
            },
        )

    def __call__(self, context: AgentContext) -> str:
        try:
            dependencies = self.dependency_map.get(self.success_target, [])
            for dependency in dependencies:
                if dependency not in context.successful_agents:
                    if dependency in context.failed_agents:
                        return self.failure_target
                    return self.wait_target
            return self.success_target
        except Exception:
            return self.failure_target

    def get_possible_targets(self) -> List[str]:
        return [self.success_target, self.wait_target, self.failure_target]


class PipelineStageRouter(RoutingFunction):
    def __init__(self, stage_map: Dict[str, str], default_target: str) -> None:
        self.stage_map = stage_map
        self.default_target = default_target

        logger.debug(
            "Initialized PipelineStageRouter",
            extra={
                "event": "router_init",
                "router": "PipelineStageRouter",
                "stage_keys": list(stage_map.keys()),
                "default_target": default_target,
            },
        )

    def __call__(self, context: AgentContext) -> str:
        try:
            current_stage = context.execution_state.get("pipeline_stage", "initial")
            return self.stage_map.get(current_stage, self.default_target)
        except Exception:
            return self.default_target

    def get_possible_targets(self) -> List[str]:
        targets = list(self.stage_map.values())
        if self.default_target not in targets:
            targets.append(self.default_target)
        return list(set(targets))
