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
    guard_node,
    data_view_node,
    answer_search_node,
    format_response_node,
    format_block_node,
    format_requires_confirmation_node,
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
        self.logger = get_logger(f"{__name__}.GraphFactory")
        self.pattern_registry = PatternRegistry()
        self.cache = GraphCache(cache_config) if cache_config else GraphCache()
        self.default_validator = default_validator

        # Available node functions mapped by agent name
        self.node_functions = {
            "refiner": refiner_node,
            "critic": critic_node,
            "historian": historian_node,
            "synthesis": synthesis_node,
            "guard": guard_node,
            "answer_search": answer_search_node,
            "format_response": format_response_node,
            "format_block": format_block_node,
            "format_requires_confirmation": format_requires_confirmation_node,
            "data_views": data_view_node,
        }

        validation_info = "with validation" if default_validator else "without validation"
        self.logger.info(
            f"GraphFactory initialized with cache, pattern registry, and {validation_info}"
        )

    def _normalize_agent_name(self, name: str) -> str:
        """
        Normalize agent aliases to the canonical node key names used in this graph.

        Canonical in this file:
          - data_views (plural)
        """
        n = (name or "").strip().lower()
        alias_map = {
            "data_view": "data_views",
            "data_views": "data_views",
        }
        return alias_map.get(n, n)

    def _normalize_agents(self, agents_to_run: List[str]) -> List[str]:
        """Normalize and de-duplicate agents while preserving order."""
        seen = set()
        out: List[str] = []
        for a in agents_to_run:
            n = self._normalize_agent_name(a)
            if not n or n in seen:
                continue
            seen.add(n)
            out.append(n)
        return out


    def _ensure_guard_pipeline(self, agents_to_run: List[str]) -> List[str]:
        """
        If guard is present, ensure the minimum routable pipeline exists:

            guard -> (allow) -> answer_search -> format_response -> END
                 -> (requires_confirmation) -> format_requires_confirmation -> END
                 -> (block/other) -> format_block -> END
        """
        agents = [self._normalize_agent_name(a) for a in agents_to_run]

        if "guard" in agents:
            # Ensure minimum pipeline exists
            for required in ["answer_search", "format_response"]:
                if required not in agents:
                    agents.append(required)

            # Ensure optional branches exist so guard can route somewhere
            for optional in ["format_block", "format_requires_confirmation"]:
                if optional not in agents:
                    agents.append(optional)

            # Guard should run first
            agents = ["guard"] + [a for a in agents if a != "guard"]

        return agents

    def _fallback_edges_linear(self, agents_to_run: List[str]) -> List[Dict[str, str]]:
        """Fallback: link agents in order and end at END."""
        if not agents_to_run:
            return []

        edges: List[Dict[str, str]] = []
        normalized = [a.lower() for a in agents_to_run]
        for i in range(len(normalized) - 1):
            edges.append({"from": normalized[i], "to": normalized[i + 1]})
        edges.append({"from": normalized[-1], "to": "END"})
        return edges

    def create_graph(self, config: GraphConfig) -> Any:
        self.logger.info(
            f"Creating graph with pattern '{config.pattern_name}' "
            f"for agents: {config.agents_to_run}"
        )

        # Normalize aliases early (data_view -> data_views, etc.)
        config.agents_to_run = self._normalize_agents(config.agents_to_run)

        # Ensure guard pipeline (and its required nodes) exist
        config.agents_to_run = self._ensure_guard_pipeline(config.agents_to_run)

        # Normalize again in case pipeline added nodes that need aliasing (future-proof)
        config.agents_to_run = self._normalize_agents(config.agents_to_run)

        # ⚠️ Defensive default:
        # If the orchestrator only asked for guard (and GraphFactory expanded to the minimal guard pipeline),
        # auto-inject data_views so "graph_data_views" workflows can actually do useful work.
        guard_pipeline_nodes = {
            "guard",
            "answer_search",
            "format_response",
            "format_block",
            "format_requires_confirmation",
        }

        current = set(config.agents_to_run)
        is_guard_only_pipeline = current == guard_pipeline_nodes

        if is_guard_only_pipeline and "data_views" not in current and "data_views" in self.node_functions:
            # after guard, before answer_search
            guard_idx = config.agents_to_run.index("guard")
            config.agents_to_run.insert(guard_idx + 1, "data_views")
            self.logger.info(
                "Injected data_views into guard-only pipeline (defensive default for data views workflows)"
            )

        try:
            if config.cache_enabled:
                cached_graph = self.cache.get_cached_graph(
                    pattern_name=config.pattern_name,
                    agents=config.agents_to_run,
                    checkpoints_enabled=config.enable_checkpoints,
                )
                if cached_graph:
                    self.logger.info("Using cached compiled graph")
                    return cached_graph

            if config.enable_validation:
                self._validate_workflow(config)

            pattern = self.pattern_registry.get_pattern(config.pattern_name)
            if not pattern:
                raise GraphBuildError(f"Unknown graph pattern: {config.pattern_name}")

            graph = self._create_state_graph(config, pattern)
            compiled_graph = self._compile_graph(graph, config)

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
        graph = StateGraph[OSSSState](state_schema=OSSSState, context_schema=OSSSContext)
        self._add_nodes(graph, config.agents_to_run)
        self._add_edges(graph, config.agents_to_run, pattern)
        return graph

    def _add_nodes(self, graph: Any, agents_to_run: List[str]) -> None:
        for agent_name in agents_to_run:
            agent_key = agent_name.lower()
            if agent_key not in self.node_functions:
                raise GraphBuildError(
                    f"Unknown agent: {agent_name}. Available agents: {sorted(self.node_functions.keys())}"
                )

            graph.add_node(agent_key, self.node_functions[agent_key])
            self.logger.debug(f"Added node: {agent_key}")

    def _add_edges(self, graph: Any, agents_to_run: List[str], pattern: GraphPattern) -> None:
        """
        Add edges to the StateGraph based on pattern.
        Falls back to a linear chain if the pattern doesn't fully describe the agent set.

        Special-case:
        - If "guard" is present, build guarded conditional pipeline.
        """
        requested = [a.lower() for a in agents_to_run]

        # ✅ Guard pipeline
        if "guard" in requested:
            graph.set_entry_point("guard")
            self.logger.debug("Set entry point: guard")

            has_data_views = "data_views" in requested
            has_synthesis = "synthesis" in requested

            def route_after_guard(state: OSSSState) -> str:
                d = (state.get("guard_decision") or "").lower()
                if d == "allow":
                    # ✅ Always go to answer_search first (never route guard directly to data_views)
                    return "answer_search"
                if d == "requires_confirmation":
                    return "format_requires_confirmation"
                return "format_block"

            graph.add_conditional_edges(
                "guard",
                route_after_guard,
                {
                    "answer_search": "answer_search",
                    "format_block": "format_block",
                    "format_requires_confirmation": "format_requires_confirmation",
                },
            )

            # ✅ Allow-path chaining
            if has_data_views:
                # Prefer answer_search -> synthesis -> data_views if synthesis exists
                if has_synthesis:
                    graph.add_edge("answer_search", "synthesis")
                    graph.add_edge("synthesis", "data_views")
                else:
                    # Safety fallback: answer_search -> data_views if synthesis isn't present
                    graph.add_edge("answer_search", "data_views")

                graph.add_edge("data_views", "format_response")
            else:
                # Normal allow path
                graph.add_edge("answer_search", "format_response")

            graph.add_edge("format_response", END)
            graph.add_edge("format_block", END)
            graph.add_edge("format_requires_confirmation", END)

            self.logger.info(
                "Guard pipeline edges added (conditional routing enabled)"
                + (" with data_views chained after answer_search" if has_data_views else "")
            )
            return

        # --- non-guard graphs use the selected pattern ---

        edges = pattern.get_edges(agents_to_run)

        edge_nodes = set()
        for e in edges:
            edge_nodes.add(e["from"])
            if e["to"] != "END":
                edge_nodes.add(e["to"])

        if any(n not in edge_nodes for n in requested):
            self.logger.warning(
                f"Pattern '{pattern.name}' edges do not cover all requested nodes; "
                f"falling back to linear edges. missing={sorted(set(requested) - edge_nodes)}"
            )
            edges = self._fallback_edges_linear(agents_to_run)

        entry_point = pattern.get_entry_point(agents_to_run)
        if not entry_point or entry_point.lower() not in requested:
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

    def _compile_graph(self, graph: StateGraph[OSSSState], config: GraphConfig) -> Any:
        try:
            if config.enable_checkpoints and config.memory_manager:
                checkpointer = config.memory_manager.get_memory_saver()
                if checkpointer:
                    compiled_graph = graph.compile(checkpointer=checkpointer)
                    self.logger.info("StateGraph compiled with memory checkpointing enabled")
                    return compiled_graph
                else:
                    self.logger.warning(
                        "Checkpointing enabled but no MemorySaver available, compiling without checkpointing"
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
        agents_to_run = self._normalize_agents(agents)

        if include_guard and "guard" not in agents_to_run:
            agents_to_run = ["guard"] + agents_to_run
        if include_data_view and "data_views" not in agents_to_run:
            agents_to_run = agents_to_run + ["data_views"]

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
        config = GraphConfig(
            agents_to_run=agents,
            enable_checkpoints=enable_checkpoints,
            memory_manager=memory_manager,
            pattern_name="parallel",
        )
        return self.create_graph(config)

    def get_cache_stats(self) -> Dict[str, Any]:
        return self.cache.get_stats()

    def clear_cache(self) -> None:
        self.cache.clear()
        self.logger.info("Graph cache cleared")

    def get_available_patterns(self) -> List[str]:
        return self.pattern_registry.get_pattern_names()

    def validate_agents(self, agents: List[str]) -> bool:
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
                raise ValidationError(f"Workflow validation failed: {error_summary}", result)

            if result.is_valid:
                self.logger.info("Workflow validation passed")

        except ValidationError:
            raise
        except Exception as e:
            raise GraphBuildError(f"Validation setup failed: {e}") from e

    def set_default_validator(self, validator: Optional[WorkflowSemanticValidator]) -> None:
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
        use_validator = validator or self.default_validator
        if not use_validator:
            return SemanticValidationResult(is_valid=True, issues=[])

        try:
            return use_validator.validate_workflow(
                agents=agents, pattern=pattern, strict_mode=strict_mode
            )
        except Exception as e:
            raise GraphBuildError(f"Validation failed: {e}") from e
