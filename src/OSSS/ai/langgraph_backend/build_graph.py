"""
Core graph building and compilation for OSSS LangGraph backend.

✅ Fix applied (Option 1: sequential action spine):
- If `data_query` is in the graph, then `synthesis` MUST NOT be reachable
  before `data_query`.
- Enforce deterministic action ordering:
    refiner -> data_query -> synthesis -> END
- Remove join/barrier (Option A) plumbing to avoid accidental "root synthesis".
"""

from typing import Dict, Any, List, Optional, Iterable
from dataclasses import dataclass

from langgraph.graph import StateGraph, END

from OSSS.ai.orchestration.state_schemas import OSSSState, OSSSContext
from OSSS.ai.orchestration.node_wrappers import (
    refiner_node,
    data_query_node,
    critic_node,
    historian_node,
    synthesis_node,
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
    PRESTEP_AGENTS = {"classifier"}
    GRAPH_CACHE_VERSION = "2025-12-23.fix3.option1.sequential.v1"

    def __init__(
        self,
        cache_config: Optional[CacheConfig] = None,
        default_validator: Optional[WorkflowSemanticValidator] = None,
    ) -> None:
        self.logger = get_logger(f"{__name__}.GraphFactory")
        self.pattern_registry = PatternRegistry()
        self.cache = GraphCache(cache_config) if cache_config else GraphCache()
        self.default_validator = default_validator

        self.node_functions = {
            "refiner": refiner_node,
            "data_query": data_query_node,
            "critic": critic_node,
            "historian": historian_node,
            "synthesis": synthesis_node,
        }

        validation_info = "with validation" if default_validator else "without validation"
        self.logger.info(
            f"GraphFactory initialized with cache, pattern registry, and {validation_info}"
        )

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------
    def _normalize_agents(self, agents: Optional[Iterable[str]]) -> List[str]:
        norm = [str(a).lower() for a in (agents or []) if a]
        return [a for a in norm if a not in self.PRESTEP_AGENTS]

    def _should_run_data_query(self, state: OSSSState) -> bool:
        """
        Uses execution_state.agent_output_meta._query_profile / query_profile if present.
        Keeps your existing behavior.
        """
        try:
            exec_state = state.get("execution_state") or {}
            if not isinstance(exec_state, dict):
                return False

            aom = exec_state.get("agent_output_meta") or {}
            if not isinstance(aom, dict):
                return False

            qp = aom.get("_query_profile") or aom.get("query_profile") or {}
            if not isinstance(qp, dict):
                return False

            intent = str(qp.get("intent", "")).lower()
            action_type = str(qp.get("action_type", qp.get("action", ""))).lower()
            is_query = bool(qp.get("is_query", False))

            if intent != "action":
                return False
            if action_type == "query":
                return True
            if is_query:
                return True
            if qp.get("table") or qp.get("tables") or qp.get("topic"):
                return True
            return False
        except Exception:
            return False

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def create_graph(self, config: GraphConfig) -> Any:
        self.logger.info(
            f"Creating graph with pattern '{config.pattern_name}' "
            f"for agents: {config.agents_to_run}"
        )

        try:
            graph_agents = self._normalize_agents(config.agents_to_run)

            if config.cache_enabled:
                cached_graph = self.cache.get_cached_graph(
                    pattern_name=config.pattern_name,
                    agents=graph_agents,
                    checkpoints_enabled=config.enable_checkpoints,
                    version=self.GRAPH_CACHE_VERSION,
                )
                if cached_graph:
                    self.logger.info("Using cached compiled graph")
                    return cached_graph

            if config.enable_validation:
                cfg_for_validation = GraphConfig(
                    agents_to_run=graph_agents,
                    enable_checkpoints=config.enable_checkpoints,
                    memory_manager=config.memory_manager,
                    pattern_name=config.pattern_name,
                    cache_enabled=config.cache_enabled,
                    enable_validation=config.enable_validation,
                    validator=config.validator,
                    validation_strict_mode=config.validation_strict_mode,
                )
                self._validate_workflow(cfg_for_validation)

            pattern = self.pattern_registry.get_pattern(config.pattern_name)
            if not pattern:
                raise GraphBuildError(f"Unknown graph pattern: {config.pattern_name}")

            graph = self._create_state_graph(config, pattern, graph_agents)
            compiled_graph = self._compile_graph(graph, config)

            if config.cache_enabled:
                self.cache.cache_graph(
                    pattern_name=config.pattern_name,
                    agents=graph_agents,
                    checkpoints_enabled=config.enable_checkpoints,
                    compiled_graph=compiled_graph,
                    version=self.GRAPH_CACHE_VERSION,
                )
                self.logger.info("Cached compiled graph for future use")

            self.logger.info(f"Successfully created graph with {len(graph_agents)} agents")
            return compiled_graph

        except Exception as e:
            error_msg = f"Failed to create graph: {e}"
            self.logger.error(error_msg)
            raise GraphBuildError(error_msg) from e

    # ---------------------------------------------------------------------
    # Graph construction
    # ---------------------------------------------------------------------
    def _create_state_graph(
        self,
        config: GraphConfig,
        pattern: GraphPattern,
        graph_agents: List[str],
    ) -> Any:
        graph = StateGraph[OSSSState](state_schema=OSSSState, context_schema=OSSSContext)

        self._add_nodes(graph, graph_agents)
        agents_set = set(a.lower() for a in graph_agents)

        edges_for_log: List[str] = []
        entry_point: Optional[str] = None

        if config.pattern_name == "conditional" and "refiner" in agents_set:
            self._add_conditional_edges(graph, graph_agents)
            edges_for_log = self._describe_conditional_plan(graph_agents)
            entry_point = "refiner"
            graph.set_entry_point(entry_point)
        else:
            edges = self._build_edges(graph_agents, pattern, config.pattern_name)

            # Deterministic entry point: if data_query is present we never start at synthesis.
            entry_point = pattern.get_entry_point(graph_agents)
            if "data_query" in agents_set:
                entry_point = "refiner" if "refiner" in agents_set else "data_query"
            if entry_point:
                graph.set_entry_point(entry_point)

            for e in edges:
                frm = e["from"]
                to = e["to"]
                graph.add_edge(frm, END if to == "END" else to)

            edges_for_log = [f"{e['from']}→{e['to']}" for e in edges]

        # Final sanity: if data_query + synthesis exist, synthesis must have an incoming
        # and must NOT be reachable before data_query in our plan (Option 1 forces it).
        if "data_query" in agents_set and "synthesis" in agents_set:
            incoming_synth = [e for e in edges_for_log if e.endswith("→synthesis")]
            if not incoming_synth:
                raise GraphBuildError(
                    "Invalid graph: synthesis has no incoming edges while data_query is present."
                )
            # Ensure no refiner→synthesis early edge leaked in
            if any(e.startswith("refiner→synthesis") for e in edges_for_log):
                raise GraphBuildError(
                    "Invalid graph: refiner→synthesis edge is present while data_query is in the graph."
                )

        self.logger.info(
            "[graph_factory] compiled graph plan",
            extra={
                "pattern": config.pattern_name,
                "nodes": graph_agents,
                "entry_point": entry_point,
                "edges": edges_for_log,
            },
        )

        return graph

    def _add_nodes(self, graph: Any, agents_to_run: List[str]) -> None:
        for agent_name in agents_to_run:
            agent_key = agent_name.lower()
            if agent_key not in self.node_functions:
                raise GraphBuildError(f"Unknown agent: {agent_name}")
            graph.add_node(agent_key, self.node_functions[agent_key])
            self.logger.debug(f"Added node: {agent_key}")

    # ---------------------------------------------------------------------
    # Standard/parallel edge building (pattern edges + overlays)
    # ---------------------------------------------------------------------
    def _build_edges(
        self,
        agents_to_run: List[str],
        pattern: GraphPattern,
        pattern_name: str,
    ) -> List[Dict[str, str]]:
        base_edges = pattern.get_edges(agents_to_run) or []

        edges: List[Dict[str, str]] = []
        for e in base_edges:
            if not isinstance(e, dict):
                continue
            frm = str(e.get("from", "")).lower()
            to = str(e.get("to", "")).lower()
            if not frm or not to:
                continue
            edges.append({"from": frm, "to": "END" if to == "end" else to})

        agents_set = set(a.lower() for a in agents_to_run)

        # ✅ Option 1: if data_query + synthesis exist, force the sequential spine.
        if "data_query" in agents_set and "synthesis" in agents_set:
            forced: List[Dict[str, str]] = []
            if "refiner" in agents_set:
                forced.append({"from": "refiner", "to": "data_query"})
            # If no refiner, caller must set entry point to data_query (handled earlier).
            forced.append({"from": "data_query", "to": "synthesis"})
            forced.append({"from": "synthesis", "to": "END"})
            return forced

        # Otherwise, keep pattern edges but apply minimal safety overlays.

        def add_edge_if_missing(frm: str, to: str) -> None:
            for existing in edges:
                if existing["from"] == frm and existing["to"] == to:
                    return
            edges.append({"from": frm, "to": to})

        if "data_query" in agents_set and "refiner" in agents_set:
            add_edge_if_missing("refiner", "data_query")

        if "synthesis" in agents_set:
            add_edge_if_missing("synthesis", "END")

        # If data_query exists but synthesis does not, end after data_query unless pattern already did.
        if "data_query" in agents_set and "synthesis" not in agents_set:
            add_edge_if_missing("data_query", "END")

        return edges

    # ---------------------------------------------------------------------
    # Conditional runtime branching
    # ---------------------------------------------------------------------
    def _add_conditional_edges(self, graph: Any, agents: List[str]) -> None:
        agents_set = set(a.lower() for a in agents)

        has_data_query = "data_query" in agents_set
        has_critic = "critic" in agents_set
        has_historian = "historian" in agents_set
        has_synthesis = "synthesis" in agents_set

        # Pick first reflection node (if any)
        reflection_start = None
        for candidate in ("critic", "historian", "synthesis"):
            if candidate in agents_set:
                reflection_start = candidate
                break

        # Refiner routes to data_query when action+query, else reflection path (or END)
        if has_data_query:
            def route_from_refiner(state: OSSSState) -> str:
                return "data_query" if self._should_run_data_query(state) else (reflection_start or "END")

            dest_map: Dict[str, Any] = {"data_query": "data_query", "END": END}
            if reflection_start:
                dest_map[reflection_start] = reflection_start

            graph.add_conditional_edges("refiner", route_from_refiner, dest_map)
        else:
            if reflection_start:
                graph.add_edge("refiner", reflection_start)
            else:
                graph.add_edge("refiner", END)

        # ✅ Option 1 conditional action spine: data_query -> synthesis (if present) else END
        if has_data_query:
            if has_synthesis:
                graph.add_edge("data_query", "synthesis")
            else:
                graph.add_edge("data_query", END)

        # Reflection wiring
        if has_synthesis:
            if has_critic:
                graph.add_edge("critic", "synthesis")
            if has_historian:
                graph.add_edge("historian", "synthesis")
            graph.add_edge("synthesis", END)
        else:
            if has_critic:
                graph.add_edge("critic", END)
            if has_historian:
                graph.add_edge("historian", END)

    def _describe_conditional_plan(self, agents: List[str]) -> List[str]:
        agents_set = set(a.lower() for a in agents)
        parts: List[str] = []

        if "data_query" in agents_set:
            parts.append("refiner→(if action+query)→data_query")
            parts.append("refiner→(else)→critic/historian/synthesis (first present)")
        if "data_query" in agents_set and "synthesis" in agents_set:
            parts.append("data_query→synthesis")
        if "critic" in agents_set and "synthesis" in agents_set:
            parts.append("critic→synthesis")
        if "historian" in agents_set and "synthesis" in agents_set:
            parts.append("historian→synthesis")
        if "synthesis" in agents_set:
            parts.append("synthesis→END")

        if not parts:
            parts.append("(no conditional edges)")
        return parts

    # ---------------------------------------------------------------------
    # Compile
    # ---------------------------------------------------------------------
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

    # ---------------------------------------------------------------------
    # Convenience builders
    # ---------------------------------------------------------------------
    def create_standard_graph(
        self,
        agents: List[str],
        enable_checkpoints: bool = False,
        memory_manager: Optional[OSSSMemoryManager] = None,
    ) -> Any:
        config = GraphConfig(
            agents_to_run=agents,
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

    def create_conditional_graph(
        self,
        agents: List[str],
        enable_checkpoints: bool = False,
        memory_manager: Optional[OSSSMemoryManager] = None,
    ) -> Any:
        config = GraphConfig(
            agents_to_run=agents,
            enable_checkpoints=enable_checkpoints,
            memory_manager=memory_manager,
            pattern_name="conditional",
        )
        return self.create_graph(config)

    # ---------------------------------------------------------------------
    # Misc
    # ---------------------------------------------------------------------
    def get_cache_stats(self) -> Dict[str, Any]:
        return self.cache.get_stats()

    def clear_cache(self) -> None:
        self.cache.clear()
        self.logger.info("Graph cache cleared")

    def get_available_patterns(self) -> List[str]:
        return self.pattern_registry.get_pattern_names()

    def validate_agents(self, agents: List[str]) -> bool:
        available_agents = set(self.node_functions.keys())
        graph_agents = self._normalize_agents(agents)

        missing_agents = set(graph_agents) - available_agents
        if missing_agents:
            self.logger.error(f"Missing agents: {missing_agents}")
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
            graph_agents = self._normalize_agents(agents)
            return use_validator.validate_workflow(
                agents=graph_agents, pattern=pattern, strict_mode=strict_mode
            )
        except Exception as e:
            raise GraphBuildError(f"Validation failed: {e}") from e
