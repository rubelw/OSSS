"""
Core graph building and compilation for OSSS LangGraph backend.

This module provides the GraphFactory class that handles StateGraph creation,
node addition, edge definition, and compilation. It separates these concerns
from orchestration logic for better maintainability and testability.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from langgraph.graph import StateGraph, END

from OSSS.ai.orchestration.state_schemas import OSSSState, OSSSContext
from OSSS.ai.orchestration.node_wrappers import (
    refiner_node,
    critic_node,
    historian_node,
    synthesis_node,
    # ✅ NEW: add these wrappers (ensure they exist in node_wrappers.py)
    guard_node,
    data_view_node,
)
from OSSS.ai.orchestration.memory_manager import OSSSMemoryManager
from OSSS.ai.observability import get_logger

from .graph_patterns import GraphPattern, PatternRegistry
from .graph_cache import GraphCache, CacheConfig
from .semantic_validation import (
    WorkflowSemanticValidator,
    ValidationError,
    SemanticValidationResult,
)


class GraphBuildError(Exception):
    """Raised when graph building fails."""

    pass


@dataclass
class GraphConfig:
    """Configuration for graph building."""

    agents_to_run: List[str]
    enable_checkpoints: bool = False
    memory_manager: Optional[OSSSMemoryManager] = None
    pattern_name: str = "standard"
    cache_enabled: bool = True
    enable_validation: bool = False
    validator: Optional[WorkflowSemanticValidator] = None
    validation_strict_mode: bool = False


class GraphFactory:
    """
    Factory class for building and compiling LangGraph StateGraphs.

    This class handles the creation of StateGraphs with proper node addition,
    edge definition, and compilation logic. It supports different graph patterns,
    caching for performance, and memory management integration.

    Features:
    - Multiple graph patterns (standard, parallel, conditional)
    - Graph compilation caching for performance
    - Memory management and checkpointing integration
    - Agent subset support for flexible execution
    """

    def __init__(
        self,
        cache_config: Optional[CacheConfig] = None,
        default_validator: Optional[WorkflowSemanticValidator] = None,
    ) -> None:
        """
        Initialize the GraphFactory.

        Parameters
        ----------
        cache_config : CacheConfig, optional
            Configuration for graph caching. If None, default config is used.
        default_validator : WorkflowSemanticValidator, optional
            Default semantic validator for workflows. If None, no validation by default.
        """
        self.logger = get_logger(f"{__name__}.GraphFactory")
        self.pattern_registry = PatternRegistry()
        self.cache = GraphCache(cache_config) if cache_config else GraphCache()
        self.default_validator = default_validator

        # Available node functions mapped by agent name
        # ✅ Added guard + data_view so they are no longer "missing"
        self.node_functions = {
            "refiner": refiner_node,
            "critic": critic_node,
            "historian": historian_node,
            "synthesis": synthesis_node,
            "guard": guard_node,
            "data_view": data_view_node,
        }

        validation_info = (
            "with validation" if default_validator else "without validation"
        )
        self.logger.info(
            f"GraphFactory initialized with cache, pattern registry, and {validation_info}"
        )


    def _fallback_edges_linear(self, agents_to_run: List[str]) -> List[Dict[str, str]]:
        """Fallback: link agents in order and end at END."""
        if not agents_to_run:
            return []
        edges: List[Dict[str, str]] = []
        for i in range(len(agents_to_run) - 1):
            edges.append({"from": agents_to_run[i].lower(), "to": agents_to_run[i + 1].lower()})
        edges.append({"from": agents_to_run[-1].lower(), "to": "END"})
        return edges


    def create_graph(self, config: GraphConfig) -> Any:
        """
        Create and compile a StateGraph based on configuration.
        """
        self.logger.info(
            f"Creating graph with pattern '{config.pattern_name}' "
            f"for agents: {config.agents_to_run}"
        )

        try:
            # Check cache first if enabled
            if config.cache_enabled:
                cached_graph = self.cache.get_cached_graph(
                    pattern_name=config.pattern_name,
                    agents=config.agents_to_run,
                    checkpoints_enabled=config.enable_checkpoints,
                )
                if cached_graph:
                    self.logger.info("Using cached compiled graph")
                    return cached_graph

            # Perform semantic validation if enabled
            if config.enable_validation:
                self._validate_workflow(config)

            # Get the pattern for graph structure
            pattern = self.pattern_registry.get_pattern(config.pattern_name)
            if not pattern:
                raise GraphBuildError(f"Unknown graph pattern: {config.pattern_name}")

            # Create the StateGraph
            graph = self._create_state_graph(config, pattern)

            # Compile the graph with optional checkpointing
            compiled_graph = self._compile_graph(graph, config)

            # Cache the compiled graph if caching is enabled
            if config.cache_enabled:
                self.cache.cache_graph(
                    pattern_name=config.pattern_name,
                    agents=config.agents_to_run,
                    checkpoints_enabled=config.enable_checkpoints,
                    compiled_graph=compiled_graph,
                )
                self.logger.info("Cached compiled graph for future use")

            self.logger.info(
                f"Successfully created graph with {len(config.agents_to_run)} agents"
            )
            return compiled_graph

        except Exception as e:
            error_msg = f"Failed to create graph: {e}"
            self.logger.error(error_msg)
            raise GraphBuildError(error_msg) from e

    def _create_state_graph(self, config: GraphConfig, pattern: GraphPattern) -> Any:
        """
        Create the StateGraph with nodes and edges.
        """
        graph = StateGraph[OSSSState](
            state_schema=OSSSState, context_schema=OSSSContext
        )

        # Add nodes for requested agents
        self._add_nodes(graph, config.agents_to_run)

        # Define graph structure using pattern
        self._add_edges(graph, config.agents_to_run, pattern)

        return graph

    def _add_nodes(self, graph: Any, agents_to_run: List[str]) -> None:
        """
        Add agent nodes to the StateGraph.
        """
        for agent_name in agents_to_run:
            agent_key = agent_name.lower()
            if agent_key not in self.node_functions:
                raise GraphBuildError(
                    f"Unknown agent: {agent_name}. Available agents: {sorted(self.node_functions.keys())}"
                )

            node_function = self.node_functions[agent_key]
            graph.add_node(agent_key, node_function)
            self.logger.debug(f"Added node: {agent_key}")

    def _add_edges(
            self, graph: Any, agents_to_run: List[str], pattern: GraphPattern
    ) -> None:
        """
        Add edges to the StateGraph based on pattern.
        Falls back to a linear chain if the pattern doesn't fully describe the agent set.
        """
        edges = pattern.get_edges(agents_to_run)

        # Validate edges cover nodes; if not, fallback
        requested = [a.lower() for a in agents_to_run]
        edge_nodes = set()
        for e in edges:
            edge_nodes.add(e["from"])
            if e["to"] != "END":
                edge_nodes.add(e["to"])

        # If pattern didn't mention some requested nodes, use a safe fallback
        if any(n not in edge_nodes for n in requested):
            self.logger.warning(
                f"Pattern '{pattern.name}' edges do not cover all requested nodes; "
                f"falling back to linear edges. missing={sorted(set(requested) - edge_nodes)}"
            )
            edges = self._fallback_edges_linear(agents_to_run)

        entry_point = pattern.get_entry_point(agents_to_run)
        if not entry_point or entry_point.lower() not in requested:
            # If pattern doesn't give an entrypoint (or gives a bad one), fallback
            entry_point = requested[0] if requested else None

        if entry_point:
            graph.set_entry_point(entry_point)
            self.logger.debug(f"Set entry point: {entry_point}")

        for edge in edges:
            if edge["to"] == "END":
                graph.add_edge(edge["from"], END)
            else:
                graph.add_edge(edge["from"], edge["to"])
            self.logger.debug(f"Added edge: {edge['from']} → {edge['to']}")

    def _compile_graph(
        self, graph: StateGraph[OSSSState], config: GraphConfig
    ) -> Any:
        """
        Compile the StateGraph with optional memory checkpointing.
        """
        try:
            if config.enable_checkpoints and config.memory_manager:
                checkpointer = config.memory_manager.get_memory_saver()
                if checkpointer:
                    compiled_graph = graph.compile(checkpointer=checkpointer)
                    self.logger.info(
                        "StateGraph compiled with memory checkpointing enabled"
                    )
                    return compiled_graph
                else:
                    self.logger.warning(
                        "Checkpointing enabled but no MemorySaver available, "
                        "compiling without checkpointing"
                    )

            compiled_graph = graph.compile()
            self.logger.info("StateGraph compiled without checkpointing")
            return compiled_graph

        except Exception as e:
            raise GraphBuildError(f"Graph compilation failed: {e}") from e

    def create_standard_graph(
            self,
            agents: List[str],
            enable_checkpoints: bool = False,
            memory_manager: Optional[OSSSMemoryManager] = None,
            include_guard: bool = False,
            include_data_view: bool = False,
    ) -> Any:
        """
        Create a standard graph pattern.
        """
        agents_to_run = [a.lower() for a in agents]

        if include_guard and "guard" not in agents_to_run:
            agents_to_run = ["guard"] + agents_to_run  # guard first
        if include_data_view and "data_view" not in agents_to_run:
            agents_to_run = agents_to_run + ["data_view"]  # data_view last

        config = GraphConfig(
            agents_to_run=agents_to_run,
            enable_checkpoints=enable_checkpoints,
            memory_manager=memory_manager,
            pattern_name="standard",
        )
        return self.create_graph(config)

    def create_parallel_graph(
        self,
        agents: List[str],
        enable_checkpoints: bool = False,
        memory_manager: Optional[OSSSMemoryManager] = None,
    ) -> Any:
        """
        Create a parallel execution graph pattern.
        """
        config = GraphConfig(
            agents_to_run=agents,
            enable_checkpoints=enable_checkpoints,
            memory_manager=memory_manager,
            pattern_name="parallel",
        )
        return self.create_graph(config)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()

    def clear_cache(self) -> None:
        """Clear the graph compilation cache."""
        self.cache.clear()
        self.logger.info("Graph cache cleared")

    def get_available_patterns(self) -> List[str]:
        """Get list of available graph patterns."""
        return self.pattern_registry.get_pattern_names()

    def validate_agents(self, agents: List[str]) -> bool:
        """
        Validate that all requested agents are available.
        """
        available_agents = set(self.node_functions.keys())
        requested_agents = set(agent.lower() for agent in agents)

        missing_agents = requested_agents - available_agents
        if missing_agents:
            self.logger.error(
                f"Missing agents: {missing_agents}. Available agents: {sorted(available_agents)}"
            )
            return False

        return True

    def _validate_workflow(self, config: GraphConfig) -> None:
        """
        Perform semantic validation on the workflow configuration.
        """
        validator = config.validator or self.default_validator

        if not validator:
            self.logger.warning("Validation enabled but no validator available")
            return

        try:
            result = validator.validate_workflow(
                agents=config.agents_to_run,
                pattern=config.pattern_name,
                strict_mode=config.validation_strict_mode,
            )

            if result.has_warnings:
                for warning in result.warning_messages:
                    self.logger.warning(f"Validation warning: {warning}")

            if result.has_errors:
                error_summary = "; ".join(result.error_messages)
                self.logger.error(f"Validation failed: {error_summary}")
                raise ValidationError(
                    f"Workflow validation failed: {error_summary}", result
                )

            if result.is_valid:
                self.logger.info("Workflow validation passed")

        except ValidationError:
            raise
        except Exception as e:
            raise GraphBuildError(f"Validation setup failed: {e}") from e

    def set_default_validator(
        self, validator: Optional[WorkflowSemanticValidator]
    ) -> None:
        """
        Set the default semantic validator for the factory.
        """
        self.default_validator = validator
        validation_info = "enabled" if validator else "disabled"
        self.logger.info(f"Default validation {validation_info}")

    def validate_workflow(
        self,
        agents: List[str],
        pattern: str,
        validator: Optional[WorkflowSemanticValidator] = None,
        strict_mode: bool = False,
    ) -> SemanticValidationResult:
        """
        Validate a workflow configuration without building the graph.
        """
        use_validator = validator or self.default_validator

        if not use_validator:
            return SemanticValidationResult(is_valid=True, issues=[])

        try:
            return use_validator.validate_workflow(
                agents=agents, pattern=pattern, strict_mode=strict_mode
            )
        except Exception as e:
            raise GraphBuildError(f"Validation failed: {e}") from e
