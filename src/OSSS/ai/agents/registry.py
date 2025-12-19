"""
Agent Registry for dynamic agent registration and creation.

This module provides a centralized registry for managing agent types,
their dependencies, and creation logic. It enables dynamic agent loading
while maintaining type safety and proper dependency injection.
"""

from typing import Dict, Type, Optional, List, Literal, Any, cast

from OSSS.ai.agents.base_agent import BaseAgent
from OSSS.ai.llm.llm_interface import LLMInterface
from OSSS.ai.exceptions import (
    DependencyResolutionError,
    FailurePropagationStrategy,
)
from OSSS.ai.agents.metadata import AgentMetadata
from OSSS.ai.agents.protocols import (
    AgentConstructorPattern,
    LLMRequiredAgentProtocol,
    LLMOptionalAgentProtocol,
    StandardAgentProtocol,
    FlexibleAgentProtocol,
    AgentWithLLMProtocol,
)


class AgentRegistry:
    """
    Central registry for managing agent types and creation.

    This registry provides a clean abstraction for agent management,
    supporting both the current architecture and future dynamic loading
    capabilities (e.g., LangGraph integration).
    """

    def __init__(self, *, data_views: Optional[dict] = None) -> None:
        self._agents: Dict[str, AgentMetadata] = {}
        self._register_core_agents()
        # ✅ Holds the configured data views used by DataViewAgent (and any other agent expecting it)
        self._data_views: dict = data_views or {}


    def set_data_views(self, data_views: dict) -> None:
        self._data_views = data_views or {}

    def _maybe_inject_constructor_kwargs(
            self, agent_cls: Type[BaseAgent], kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Inject required constructor kwargs that are registry-owned (ex: data_views)
        when they are missing from caller-provided kwargs.
        """
        import inspect

        try:
            sig = inspect.signature(agent_cls.__init__)
            params = sig.parameters

            # ✅ Inject required kw-only "data_views" if constructor requires it
            if "data_views" in params and "data_views" not in kwargs:
                p = params["data_views"]
                required = (
                        p.default == inspect.Parameter.empty
                        and p.kind in (
                            inspect.Parameter.KEYWORD_ONLY,
                            inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        )
                )
                if required:
                    kwargs = dict(kwargs)
                    kwargs["data_views"] = self._data_views
        except Exception:
            # If inspection fails, don't block agent creation—just don't inject.
            pass

        return kwargs

    def register(
        self,
        name: str,
        agent_class: Type[BaseAgent],
        requires_llm: bool = False,
        constructor_pattern: Optional[AgentConstructorPattern] = None,
        description: str = "",
        dependencies: Optional[List[str]] = None,
        is_critical: bool = True,
        failure_strategy: FailurePropagationStrategy = FailurePropagationStrategy.FAIL_FAST,
        fallback_agents: Optional[List[str]] = None,
        health_checks: Optional[List[str]] = None,
        # New multi-axis classification parameters
        cognitive_speed: Literal["fast", "slow", "adaptive"] = "adaptive",
        cognitive_depth: Literal["shallow", "deep", "variable"] = "variable",
        processing_pattern: Literal["atomic", "composite", "chain"] = "atomic",
        primary_capability: str = "",
        secondary_capabilities: Optional[List[str]] = None,
        pipeline_role: Literal[
            "entry", "intermediate", "terminal", "standalone"
        ] = "standalone",
        bounded_context: str = "reflection",
    ) -> None:
        """
        Register an agent type with the registry.
        """
        if name in self._agents:
            raise ValueError(f"Agent '{name}' is already registered")

        # Auto-detect constructor pattern if not provided
        if constructor_pattern is None:
            constructor_pattern = self._detect_constructor_pattern(
                agent_class, requires_llm
            )

        metadata = AgentMetadata.create_for_registry(
            name=name,
            agent_class=agent_class,
            requires_llm=requires_llm,
            constructor_pattern=constructor_pattern,
            description=description,
            dependencies=dependencies,
            is_critical=is_critical,
            failure_strategy=failure_strategy,
            fallback_agents=fallback_agents,
            health_checks=health_checks,
            # Multi-axis classification
            cognitive_speed=cognitive_speed,
            cognitive_depth=cognitive_depth,
            processing_pattern=processing_pattern,
            primary_capability=primary_capability,
            secondary_capabilities=secondary_capabilities,
            pipeline_role=pipeline_role,
            bounded_context=bounded_context,
        )
        self._agents[name] = metadata

    def create_agent(
        self, name: str, llm: Optional[LLMInterface] = None, **kwargs: Any
    ) -> BaseAgent:
        """
        Create an agent instance by name.
        """
        if name not in self._agents:
            raise ValueError(
                f"Unknown agent: '{name}'. Available agents: {list(self.get_available_agents())}"
            )

        metadata = self._agents[name]

        # Check LLM requirement
        if metadata.requires_llm and llm is None:
            raise ValueError(f"Agent '{name}' requires an LLM interface")

        # Create agent with appropriate parameters using protocol-based approach
        try:
            agent_cls = metadata.agent_class
            pattern = metadata.constructor_pattern

            # ✅ Inject registry-owned required kwargs (like data_views) when missing
            kwargs = self._maybe_inject_constructor_kwargs(agent_cls, dict(kwargs))

            if pattern == AgentConstructorPattern.LLM_REQUIRED:
                assert llm is not None
                agent_constructor = cast(Type[LLMRequiredAgentProtocol], agent_cls)

                import inspect

                try:
                    sig = inspect.signature(agent_cls.__init__)
                    if "name" in sig.parameters:
                        agent_instance = agent_constructor(llm=llm, name=name, **kwargs)
                    else:
                        agent_instance = agent_constructor(llm=llm, **kwargs)
                except Exception:
                    agent_instance = agent_constructor(llm=llm, **kwargs)

            elif pattern == AgentConstructorPattern.LLM_OPTIONAL:
                agent_constructor = cast(Type[LLMOptionalAgentProtocol], agent_cls)
                agent_instance = agent_constructor(llm=llm, **kwargs)  # type: ignore[arg-type]

            elif pattern == AgentConstructorPattern.STANDARD:
                agent_constructor = cast(Type[StandardAgentProtocol], agent_cls)
                agent_instance = agent_constructor(name=name, **kwargs)

            else:  # FLEXIBLE pattern
                import inspect

                try:
                    constructor_params = inspect.signature(
                        agent_cls.__init__
                    ).parameters
                    agent_constructor = cast(Type[FlexibleAgentProtocol], agent_cls)
                    if "name" in constructor_params:
                        agent_instance = agent_constructor(name=name, **kwargs)
                    elif "llm" in constructor_params and llm is not None:
                        agent_instance = agent_constructor(llm=llm, **kwargs)
                    else:
                        agent_instance = agent_constructor(**kwargs)
                except Exception:
                    agent_constructor = cast(Type[FlexibleAgentProtocol], agent_cls)
                    agent_instance = agent_constructor(**kwargs)

            if not isinstance(agent_instance, BaseAgent):
                raise ValueError(
                    f"Agent '{name}' constructor did not return a BaseAgent instance"
                )

            return agent_instance

        except Exception as e:
            raise ValueError(f"Failed to create agent '{name}': {e}") from e

    def create_agent_with_llm(
        self, name: str, llm: Optional[LLMInterface] = None, **kwargs: Any
    ) -> AgentWithLLMProtocol:
        """
        Create an agent that has an LLM attribute, with proper type hinting.
        """
        if name not in self._agents:
            raise ValueError(
                f"Unknown agent: '{name}'. Available agents: {list(self.get_available_agents())}"
            )

        metadata = self._agents[name]

        # ✅ purely metadata-based check (removed manual allowlist)
        if not (
            metadata.requires_llm
            or metadata.constructor_pattern
            in {
                AgentConstructorPattern.LLM_REQUIRED,
                AgentConstructorPattern.LLM_OPTIONAL,
            }
        ):
            raise ValueError(
                f"Agent '{name}' is not expected to have LLM attributes. "
                f"Use create_agent() for non-LLM agents."
            )

        agent = self.create_agent(name, llm, **kwargs)
        return cast(AgentWithLLMProtocol, agent)

    def get_available_agents(self) -> List[str]:
        """Get list of all registered agent names."""
        return list(self._agents.keys())

    def get_metadata(self, name: str) -> AgentMetadata:
        if name not in self._agents:
            raise ValueError(f"Unknown agent: '{name}'")
        return self._agents[name]

    def get_agent_info(self, name: str) -> AgentMetadata:
        if name not in self._agents:
            raise ValueError(f"Unknown agent: '{name}'")
        return self._agents[name]

    def get_agents_requiring_llm(self) -> List[str]:
        return [
            name for name, metadata in self._agents.items() if metadata.requires_llm
        ]

    def validate_pipeline(self, agent_names: List[str]) -> bool:
        for name in agent_names:
            if name not in self._agents:
                return False

        try:
            self.resolve_dependencies(agent_names)
            return True
        except DependencyResolutionError:
            return False

    def resolve_dependencies(self, agent_names: List[str]) -> List[str]:
        dependency_graph = {}
        for name in agent_names:
            if name in self._agents:
                deps = self._agents[name].dependencies
                dependency_graph[name] = deps.copy() if deps is not None else []
            else:
                dependency_graph[name] = []

        in_degree = {name: 0 for name in agent_names}
        for name in agent_names:
            for dep in dependency_graph[name]:
                if dep in in_degree:
                    in_degree[name] += 1

        queue = [name for name in agent_names if in_degree[name] == 0]
        result = []

        while queue:
            current = queue.pop(0)
            result.append(current)

            for neighbor in agent_names:
                if current in dependency_graph[neighbor]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

        if len(result) != len(agent_names):
            remaining = [name for name in agent_names if name not in result]
            raise DependencyResolutionError(
                dependency_issue="Circular dependency detected",
                affected_agents=remaining,
                dependency_graph=dependency_graph,
            )

        return result

    def check_health(self, agent_name: str) -> bool:
        if agent_name not in self._agents:
            return True

        metadata = self._agents[agent_name]
        if metadata.requires_llm:
            pass
        return True

    def get_fallback_agents(self, agent_name: str) -> List[str]:
        if agent_name not in self._agents:
            return []
        fallback = self._agents[agent_name].fallback_agents
        return fallback.copy() if fallback is not None else []

    def get_failure_strategy(self, agent_name: str) -> FailurePropagationStrategy:
        if agent_name not in self._agents:
            return FailurePropagationStrategy.FAIL_FAST
        return self._agents[agent_name].failure_strategy

    def is_critical_agent(self, agent_name: str) -> bool:
        if agent_name not in self._agents:
            return True
        return self._agents[agent_name].is_critical

    def get_agent_metadata(self, agent_name: str) -> Optional[AgentMetadata]:
        return self._agents.get(agent_name)

    def _detect_constructor_pattern(
        self, agent_class: Type[BaseAgent], requires_llm: bool
    ) -> AgentConstructorPattern:
        import inspect

        try:
            sig = inspect.signature(agent_class.__init__)
            params = list(sig.parameters.keys())
            params = [p for p in params if p != "self"]

            if not params:
                return AgentConstructorPattern.FLEXIBLE

            first_param = params[0]

            if first_param == "llm":
                param = sig.parameters[first_param]
                if param.default == inspect.Parameter.empty and requires_llm:
                    return AgentConstructorPattern.LLM_REQUIRED
                else:
                    return AgentConstructorPattern.LLM_OPTIONAL
            elif first_param == "name":
                return AgentConstructorPattern.STANDARD
            else:
                return AgentConstructorPattern.FLEXIBLE

        except Exception:
            return AgentConstructorPattern.FLEXIBLE

    def _register_core_agents(self) -> None:
        """Register the core agents that ship with OSSS with conditional execution support."""
        from OSSS.ai.agents.refiner.agent import RefinerAgent
        from OSSS.ai.agents.critic.agent import CriticAgent
        from OSSS.ai.agents.historian.agent import HistorianAgent
        from OSSS.ai.agents.synthesis.agent import SynthesisAgent
        from OSSS.ai.agents.guard.agent import GuardAgent
        from OSSS.ai.agents.data_views.agent import DataViewAgent
        from OSSS.ai.agents.answer_search.agent import AnswerSearchAgent

        from OSSS.ai.agents.metadata import AgentMetadata
        from OSSS.ai.agents.base_agent import BaseAgent

        AgentMetadata.model_rebuild(_types_namespace={"BaseAgent": BaseAgent})

        self.register(
            name="refiner",
            agent_class=RefinerAgent,
            requires_llm=True,
            description="Refines and improves user queries for better processing",
            dependencies=[],
            is_critical=True,
            failure_strategy=FailurePropagationStrategy.FAIL_FAST,
            fallback_agents=[],
            cognitive_speed="slow",
            cognitive_depth="deep",
            processing_pattern="atomic",
            primary_capability="intent_clarification",
            secondary_capabilities=["prompt_structuring", "scope_definition"],
            pipeline_role="entry",
            bounded_context="reflection",
        )

        self.register(
            name="critic",
            agent_class=CriticAgent,
            requires_llm=True,
            description="Analyzes refined queries to identify assumptions, gaps, and biases",
            dependencies=["refiner"],
            is_critical=False,
            failure_strategy=FailurePropagationStrategy.GRACEFUL_DEGRADATION,
            fallback_agents=[],
            cognitive_speed="slow",
            cognitive_depth="deep",
            processing_pattern="composite",
            primary_capability="critical_analysis",
            secondary_capabilities=["assumption_identification", "bias_detection"],
            pipeline_role="intermediate",
            bounded_context="reflection",
        )

        self.register(
            name="historian",
            agent_class=HistorianAgent,
            requires_llm=True,
            description="Retrieves relevant historical context and information",
            dependencies=[],
            is_critical=False,
            failure_strategy=FailurePropagationStrategy.WARN_CONTINUE,
            fallback_agents=[],
            cognitive_speed="adaptive",
            cognitive_depth="variable",
            processing_pattern="composite",
            primary_capability="context_retrieval",
            secondary_capabilities=["memory_search", "relevance_ranking"],
            pipeline_role="intermediate",
            bounded_context="retrieval",
        )

        self.register(
            name="synthesis",
            agent_class=SynthesisAgent,
            requires_llm=True,
            description="Synthesizes outputs from multiple agents into final response",
            dependencies=[],
            is_critical=True,
            failure_strategy=FailurePropagationStrategy.CONDITIONAL_FALLBACK,
            fallback_agents=[],
            cognitive_speed="slow",
            cognitive_depth="deep",
            processing_pattern="chain",
            primary_capability="multi_perspective_synthesis",
            secondary_capabilities=["conflict_resolution", "theme_identification"],
            pipeline_role="terminal",
            bounded_context="reflection",
        )

        # ✅ Guard agent
        self.register(
            name="guard",
            agent_class=GuardAgent,
            requires_llm=True,
            description="Policy/safety guardrail checks (allow/deny/require-confirmation)",
            dependencies=[],
            is_critical=True,
            failure_strategy=FailurePropagationStrategy.FAIL_FAST,
            fallback_agents=[],
            cognitive_speed="fast",
            cognitive_depth="shallow",
            processing_pattern="atomic",
            primary_capability="policy_guardrails",
            secondary_capabilities=["risk_flagging", "action_gating"],
            pipeline_role="standalone",
            bounded_context="reflection",
        )

        # ✅ DataView agent
        self.register(
            name="data_views",
            agent_class=DataViewAgent,
            requires_llm=True,
            description="Generates structured data views / table-oriented responses from OSSS models",
            dependencies=[],
            is_critical=False,
            failure_strategy=FailurePropagationStrategy.WARN_CONTINUE,
            fallback_agents=[],
            cognitive_speed="adaptive",
            cognitive_depth="variable",
            processing_pattern="composite",
            primary_capability="data_view_generation",
            secondary_capabilities=["entity_listing", "schema_reasoning"],
            pipeline_role="standalone",
            bounded_context="retrieval",
        )

        self.register(
            name="answer_search",
            agent_class=AnswerSearchAgent,
            requires_llm=True,
            description="Executes the answer/search step after guard allows the request",
            dependencies=["guard"],
            is_critical=True,
            failure_strategy=FailurePropagationStrategy.CONDITIONAL_FALLBACK,
            fallback_agents=["synthesis"],
            cognitive_speed="adaptive",
            cognitive_depth="variable",
            processing_pattern="composite",
            primary_capability="answer_generation",
            secondary_capabilities=["information_retrieval", "citation_assembly"],
            pipeline_role="intermediate",
            bounded_context="retrieval",
        )


# Global registry instance
_global_registry = None


def get_agent_registry() -> AgentRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = AgentRegistry()
    return _global_registry


def register_agent(
    name: str,
    agent_class: Type[BaseAgent],
    requires_llm: bool = False,
    constructor_pattern: Optional[AgentConstructorPattern] = None,
    description: str = "",
    dependencies: Optional[List[str]] = None,
    is_critical: bool = True,
    failure_strategy: FailurePropagationStrategy = FailurePropagationStrategy.FAIL_FAST,
    fallback_agents: Optional[List[str]] = None,
    health_checks: Optional[List[str]] = None,
    cognitive_speed: Literal["fast", "slow", "adaptive"] = "adaptive",
    cognitive_depth: Literal["shallow", "deep", "variable"] = "variable",
    processing_pattern: Literal["atomic", "composite", "chain"] = "atomic",
    primary_capability: str = "",
    secondary_capabilities: Optional[List[str]] = None,
    pipeline_role: Literal[
        "entry", "intermediate", "terminal", "standalone"
    ] = "standalone",
    bounded_context: str = "reflection",
) -> None:
    registry = get_agent_registry()
    registry.register(
        name,
        agent_class,
        requires_llm,
        constructor_pattern,
        description,
        dependencies,
        is_critical,
        failure_strategy,
        fallback_agents,
        health_checks,
        cognitive_speed,
        cognitive_depth,
        processing_pattern,
        primary_capability,
        secondary_capabilities,
        pipeline_role,
        bounded_context,
    )


def create_agent(
    name: str, llm: Optional[LLMInterface] = None, **kwargs: Any
) -> BaseAgent:
    registry = get_agent_registry()
    return registry.create_agent(name, llm, **kwargs)


def create_agent_with_llm(
    name: str, llm: Optional[LLMInterface] = None, **kwargs: Any
) -> AgentWithLLMProtocol:
    registry = get_agent_registry()
    return registry.create_agent_with_llm(name, llm, **kwargs)


def get_agent_metadata(name: str) -> Optional[AgentMetadata]:
    registry = get_agent_registry()
    return registry.get_agent_metadata(name)
