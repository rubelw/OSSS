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
    data_view_node,  # canonical wrapper maps to "data_views"
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

    # 🚨 IMPORTANT:
    # Factory must NOT silently mutate workflow plans.
    # Preflight / workflow templates own the plan.
    allow_auto_inject_nodes: bool = False


class GraphFactory:
    """
    Factory class for building and compiling LangGraph StateGraphs.
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

        # Canonical node functions
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

        self._allow_auto_inject_nodes = False

        self.logger.info("GraphFactory initialized")

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def validate_agents(self, agents: List[str]) -> bool:
        """
        Validate that all requested agent names exist in node_functions.

        Orchestrator uses this to fail fast before attempting graph build.
        """
        available_agents = set(self.node_functions.keys())
        requested_agents = set((a or "").lower() for a in (agents or []))

        missing_agents = requested_agents - available_agents
        if missing_agents:
            self.logger.error(
                "Missing agents for graph build",
                extra={
                    "missing_agents": sorted(missing_agents),
                    "available_agents": sorted(available_agents),
                },
            )
            return False
        return True


    def _normalize_agent_name(self, name: str) -> str:
        n = (name or "").strip().lower()
        return {
            "data_view": "data_views",
            "data_views": "data_views",
        }.get(n, n)

    def _normalize_agents(self, agents: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for a in agents:
            n = self._normalize_agent_name(a)
            if n and n not in seen:
                seen.add(n)
                out.append(n)
        return out

    # ------------------------------------------------------------------
    # Guard pipeline enforcement
    # ------------------------------------------------------------------

    def _ensure_guard_pipeline(self, agents: List[str]) -> List[str]:
        """
        Guard routing MUST be explicit.

        If guard is present:
        - When allow_auto_inject_nodes=False (default):
            * Validate that required routing nodes exist
            * FAIL FAST if missing
        - When allow_auto_inject_nodes=True:
            * Inject missing routing nodes
        """
        if "guard" not in agents:
            return agents

        required = ["answer_search", "format_response"]
        optional = ["format_block", "format_requires_confirmation"]

        missing_required = [n for n in required if n not in agents]
        missing_optional = [n for n in optional if n not in agents]

        if not self._allow_auto_inject_nodes:
            if missing_required or missing_optional:
                raise GraphBuildError(
                    "Guard pipeline incomplete and auto-inject disabled. "
                    f"missing_required={missing_required}, "
                    f"missing_optional={missing_optional}. "
                    "Fix workflow template or enable allow_auto_inject_nodes."
                )
        else:
            for n in required + optional:
                if n not in agents:
                    agents.append(n)

        # Guard must be first
        return ["guard"] + [a for a in agents if a != "guard"]

    # ------------------------------------------------------------------
    # Graph creation
    # ------------------------------------------------------------------

    def create_graph(self, config: GraphConfig) -> Any:
        self.logger.info(
            f"Creating graph pattern={config.pattern_name} agents={config.agents_to_run}"
        )

        # Respect caller intent
        self._allow_auto_inject_nodes = bool(config.allow_auto_inject_nodes)

        agents = self._normalize_agents(config.agents_to_run)
        agents = self._ensure_guard_pipeline(agents)
        agents = self._normalize_agents(agents)

        if config.cache_enabled:
            cached = self.cache.get_cached_graph(
                pattern_name=config.pattern_name,
                agents=agents,
                checkpoints_enabled=config.enable_checkpoints,
            )
            if cached:
                self.logger.info("Using cached graph")
                return cached

        if config.enable_validation:
            self._validate_workflow(config)

        pattern = self.pattern_registry.get_pattern(config.pattern_name)
        if not pattern:
            raise GraphBuildError(f"Unknown graph pattern: {config.pattern_name}")

        graph = StateGraph[OSSSState](
            state_schema=OSSSState,
            context_schema=OSSSContext,
        )

        self._add_nodes(graph, agents)
        self._add_edges(graph, agents, pattern)

        compiled = self._compile_graph(graph, config)

        if config.cache_enabled:
            self.cache.cache_graph(
                pattern_name=config.pattern_name,
                agents=agents,
                checkpoints_enabled=config.enable_checkpoints,
                compiled_graph=compiled,
            )

        self.logger.info(f"Graph created successfully ({len(agents)} nodes)")
        return compiled

    # ------------------------------------------------------------------
    # Node + edge wiring
    # ------------------------------------------------------------------

    def _add_nodes(self, graph: Any, agents: List[str]) -> None:
        for a in agents:
            if a not in self.node_functions:
                raise GraphBuildError(
                    f"Unknown agent '{a}'. Available: {sorted(self.node_functions)}"
                )
            graph.add_node(a, self.node_functions[a])
            self.logger.debug(f"Added node: {a}")

    def _add_edges(self, graph: Any, agents: List[str], pattern: GraphPattern) -> None:
        if "guard" in agents:
            graph.set_entry_point("guard")

            def route_after_guard(state: OSSSState) -> str:
                decision = (state.get("guard_decision") or "").lower()
                if decision == "allow":
                    return "answer_search"
                if decision == "requires_confirmation":
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

            if "data_views" in agents:
                if "synthesis" in agents:
                    graph.add_edge("answer_search", "synthesis")
                    graph.add_edge("synthesis", "data_views")
                else:
                    graph.add_edge("answer_search", "data_views")

                graph.add_edge("data_views", "format_response")
            else:
                graph.add_edge("answer_search", "format_response")

            graph.add_edge("format_response", END)
            graph.add_edge("format_block", END)
            graph.add_edge("format_requires_confirmation", END)
            return

        # Non-guard graphs
        edges = pattern.get_edges(agents)
        for e in edges:
            graph.add_edge(e["from"], END if e["to"] == "END" else e["to"])

        entry = pattern.get_entry_point(agents)
        if entry:
            graph.set_entry_point(entry)

    # ------------------------------------------------------------------
    # Compilation
    # ------------------------------------------------------------------

    def _compile_graph(self, graph: StateGraph, config: GraphConfig) -> Any:
        if config.enable_checkpoints and config.memory_manager:
            saver = config.memory_manager.get_memory_saver()
            if saver:
                return graph.compile(checkpointer=saver)

        return graph.compile()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_workflow(self, config: GraphConfig) -> None:
        validator = config.validator or self.default_validator
        if not validator:
            return

        result = validator.validate_workflow(
            agents=config.agents_to_run,
            pattern=config.pattern_name,
            strict_mode=config.validation_strict_mode,
        )

        if result.has_errors:
            raise ValidationError(
                "; ".join(result.error_messages), result
            )
