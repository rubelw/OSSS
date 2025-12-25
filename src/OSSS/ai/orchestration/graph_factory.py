"""
Core graph building and compilation for OSSS LangGraph backend.

Goals:
- Make graph patterns + edges configurable via JSON (graph-patterns.json)
- Keep a sane default "standard" pattern:
    refiner -> (critic, historian) -> synthesis -> END
- Support conditional routing via named routers (router registry)
- Keep GraphFactory as the ONLY place that mutates LangGraph StateGraph
- Preserve: caching, optional checkpointing, optional semantic validation

Option A (✅ implemented here):
- Planning happens BEFORE graph compilation.
- GraphFactory reads/writes ONLY execution_state planning artifacts:
    - execution_state["execution_config"]["graph_pattern"]
    - execution_state["planned_agents"]
- GraphFactory must honor planned_agents as the source-of-truth for which nodes exist.
- route_gate_node must NOT mutate planning (it’s too late once the graph is compiled).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, Iterable, List, Optional
import os
import pathlib
import hashlib

from langgraph.graph import StateGraph, END

from OSSS.ai.orchestration.state_schemas import OSSSState, OSSSContext
from OSSS.ai.orchestration.node_wrappers import (
    refiner_node,
    data_query_node,
    critic_node,
    historian_node,
    synthesis_node,
    final_node,
    apply_option_a_fastpath_planning,
)
from OSSS.ai.orchestration.memory_manager import OSSSMemoryManager
from OSSS.ai.observability import get_logger

from .graph_cache import GraphCache, CacheConfig
from .semantic_validation import (
    WorkflowSemanticValidator,
    ValidationError,
)
from .patterns.spec import PatternRegistry, RouterRegistry, GraphPattern

from OSSS.ai.orchestration.nodes.validator_node import ValidatorNode
from OSSS.ai.orchestration.nodes.terminator_node import TerminatorNode
from OSSS.ai.orchestration.nodes.aggregator_node import AggregatorNode
from OSSS.ai.orchestration.nodes.decision_node import DecisionNode


class GraphBuildError(Exception):
    """Raised when graph building fails."""


@dataclass
class GraphConfig:
    agents_to_run: List[str]
    pattern_name: str = "standard"
    execution_state: Optional[Dict[str, Any]] = None
    chosen_target: Optional[str] = None
    enable_checkpoints: bool = False
    memory_manager: Optional[OSSSMemoryManager] = None
    cache_enabled: bool = True
    enable_validation: bool = False
    validator: Optional[WorkflowSemanticValidator] = None
    validation_strict_mode: bool = False


class GraphFactory:
    """
    Builds a LangGraph StateGraph from:
      - a list of agents to include
      - a selected pattern (from graph-patterns.json)
      - optional conditional routing (router registry)

    IMPORTANT: this class is the ONLY place that calls:
      - graph.add_node(...)
      - graph.add_edge(...)
      - graph.add_conditional_edges(...)
      - graph.compile(...)

    Option A:
      - planning is applied via execution_state BEFORE compilation
      - planned_agents is treated as the authoritative set of nodes to add
    """

    PRESTEP_AGENTS = {"classifier"}
    DEFAULT_PATTERNS_PATH = "src/OSSS/ai/orchestration/patterns/graph-patterns.json"

    def __init__(
        self,
        *,
        cache_config: Optional[CacheConfig] = None,
        default_validator: Optional[WorkflowSemanticValidator] = None,
        patterns_path: Optional[str] = None,
        router_registry: Optional[RouterRegistry] = None,
    ) -> None:
        self.logger = get_logger(f"{__name__}.GraphFactory")
        self.cache = GraphCache(cache_config) if cache_config else GraphCache()
        self.default_validator = default_validator

        self.patterns_path = patterns_path or os.getenv("OSSS_GRAPH_PATTERNS_PATH") or self.DEFAULT_PATTERNS_PATH
        self.pattern_registry = PatternRegistry()
        self._load_patterns(self.patterns_path)

        self.routers = router_registry or RouterRegistry()
        self._register_default_routers()

        self.node_functions = {
            "refiner": refiner_node,
            "data_query": data_query_node,
            "critic": critic_node,
            "historian": historian_node,
            "synthesis": synthesis_node,
            "validator": ValidatorNode,
            "terminator": TerminatorNode,
            "aggregator": AggregatorNode,
            "decision": DecisionNode,
            # ✅ canonical terminal node is "final"
            "final": final_node,

        }

        self.logger.info(
            "GraphFactory initialized",
            extra={
                "patterns_path": self.patterns_path,
                "cache": True,
                "validation": bool(default_validator),
            },
        )

    # ------------------------------------------------------------------
    # PATTERNS
    # ------------------------------------------------------------------

    def _load_patterns(self, path: str) -> None:
        """
        Load graph patterns from JSON.
        """
        p = pathlib.Path(path)
        if not p.exists():
            raise GraphBuildError(f"Patterns file not found: {path}")
        self.pattern_registry.load_from_file(str(p))

    def _patterns_fingerprint(self) -> str:
        """
        Fingerprint patterns so cache invalidates when JSON changes.
        Safe if file missing/unreadable.
        """
        try:
            raw = pathlib.Path(self.patterns_path).read_bytes()
            return hashlib.sha256(raw).hexdigest()[:16]
        except Exception:
            return "nohash"

    # ------------------------------------------------------------------
    # ROUTERS
    # ------------------------------------------------------------------

    def _register_default_routers(self) -> None:
        """
        Register named routers used by conditional patterns.

        Router signature:
          fn(state: OSSSState) -> str   (must return a destination key)
        """

        def refiner_route_query_or_reflect(state: OSSSState) -> str:
            return "data_query" if self._should_run_data_query(state) else "reflect"

        self.routers.register("refiner_route_query_or_reflect", refiner_route_query_or_reflect)

    def _should_run_data_query(self, state: OSSSState) -> bool:
        """
        Determines if data_query should run.

        Matches existing behavior:
        uses execution_state.agent_output_meta._query_profile / query_profile if present.
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

    # ------------------------------------------------------------------
    # OPTION A — PRE-COMPILE PLANNING + STRICT NODE SET
    # ------------------------------------------------------------------

    def _ensure_execution_config(self, exec_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure exec_state["execution_config"] exists and is a dict.
        """
        ec = exec_state.get("execution_config")
        if not isinstance(ec, dict):
            ec = {}
            exec_state["execution_config"] = ec
        return ec

    def _apply_option_a_planning_bridge(self, cfg: GraphConfig) -> GraphConfig:
        """
        Option A bridge:
          - call apply_option_a_fastpath_planning BEFORE compilation
          - adopt exec_state.execution_config.graph_pattern into cfg.pattern_name
          - adopt exec_state.planned_agents into cfg.agents_to_run (authoritative)
        """
        exec_state = cfg.execution_state
        if not isinstance(exec_state, dict):
            return cfg

        chosen_target = cfg.chosen_target or exec_state.get("route")
        if not isinstance(chosen_target, str):
            chosen_target = ""

        # ✅ Option A: decide pattern + planned agents BEFORE compilation
        apply_option_a_fastpath_planning(exec_state=exec_state, chosen_target=chosen_target or "refiner")

        ec = self._ensure_execution_config(exec_state)

        # ✅ Ensure refiner_final implies refiner->output node set
        if ec.get("graph_pattern") == "refiner_final":
            exec_state["planned_agents"] = ["refiner", "final"]

        # ✅ If caller didn’t pass pattern_name, adopt computed graph_pattern
        gp = ec.get("graph_pattern")
        if isinstance(gp, str) and gp:
            cfg = replace(cfg, pattern_name=gp)

        # ✅ planned_agents is authoritative for which nodes exist
        planned = exec_state.get("planned_agents")
        if isinstance(planned, list) and planned:
            cfg = replace(cfg, agents_to_run=[str(a).lower() for a in planned if a])

        return cfg

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def create_graph(self, config: GraphConfig) -> Any:
        try:
            # 🔑 Option A order:
            #   1) apply planning bridge (may change pattern + planned agents)
            #   2) normalize agents for selected pattern (still enforces invariants)
            config = self._apply_option_a_planning_bridge(config)
            config = self.prepare_config(config)

            graph_agents = list(config.agents_to_run or [])

            pattern = self.pattern_registry.get(config.pattern_name)
            if not pattern:
                raise GraphBuildError(f"Unknown graph pattern: {config.pattern_name}")

            # Optional semantic validation BEFORE graph creation (preserved)
            if config.enable_validation:
                validator = config.validator or self.default_validator
                if validator:
                    result = validator.validate_workflow(
                        agents=graph_agents,
                        pattern=config.pattern_name,
                        strict_mode=config.validation_strict_mode,
                    )
                    if result.has_errors:
                        summary = "; ".join(result.error_messages)
                        raise ValidationError(f"Workflow validation failed: {summary}", result)
                else:
                    self.logger.warning("Validation enabled but no validator available")

            cache_version = self._cache_version(config.pattern_name, graph_agents, config.enable_checkpoints)

            if config.cache_enabled:
                cached = self.cache.get_cached_graph(
                    pattern_name=config.pattern_name,
                    agents=graph_agents,
                    checkpoints_enabled=config.enable_checkpoints,
                    version=cache_version,
                )
                if cached:
                    return cached

            graph = self._create_state_graph(config, pattern, graph_agents)
            compiled = self._compile_graph(graph, config)

            if config.cache_enabled:
                self.cache.cache_graph(
                    pattern_name=config.pattern_name,
                    agents=graph_agents,
                    checkpoints_enabled=config.enable_checkpoints,
                    compiled_graph=compiled,
                    version=cache_version,
                )

            return compiled

        except ValidationError:
            raise
        except Exception as e:
            raise GraphBuildError(f"Failed to create graph: {e}") from e

    # ------------------------------------------------------------------
    # NORMALIZATION (PATTERN-AWARE)
    # ------------------------------------------------------------------

    def _is_terminal_output_pattern(self, pattern_name: str) -> bool:
        return pattern_name.lower() in {"refiner_final", "refiner_only_output", "minimal"}

    def _normalize_agents_for_pattern(self, agents: Iterable[str], pattern_name: str) -> List[str]:
        a = [str(x).lower() for x in (agents or []) if x]
        a = [x for x in a if x not in self.PRESTEP_AGENTS]

        # Always ensure refiner first
        if "refiner" not in a:
            a.insert(0, "refiner")

        # Decide terminal vs normal execution
        terminal = self._is_terminal_output_pattern(pattern_name) or ("final" in a)

        if terminal:
            # Terminal flows MUST end with output and MUST NOT include synthesis
            a = [x for x in a if x != "synthesis"]
            if "final" not in a:
                a.append("final")
        else:
            # Normal flows MUST end with synthesis and MUST NOT include output
            a = [x for x in a if x != "final"]
            if "synthesis" not in a:
                a.append("synthesis")

        # If data_query runs, skip critic/historian entirely
        if "data_query" in a:
            a = [x for x in a if x not in ("critic", "historian")]

        # Stable de-dupe preserving order
        out: List[str] = []
        seen = set()
        for x in a:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    def prepare_config(self, cfg: GraphConfig) -> GraphConfig:
        deduped = self._normalize_agents_for_pattern(cfg.agents_to_run, cfg.pattern_name)

        # Hard safety: standard must not run output
        if cfg.pattern_name.lower() == "standard":
            deduped = [a for a in deduped if a != "final"]

        if deduped == list(cfg.agents_to_run or []):
            return cfg
        return replace(cfg, agents_to_run=deduped)

    # ------------------------------------------------------------------
    # GRAPH BUILDING
    # ------------------------------------------------------------------

    def _create_state_graph(self, config: GraphConfig, pattern: GraphPattern, graph_agents: List[str]) -> Any:
        graph = StateGraph[OSSSState](state_schema=OSSSState, context_schema=OSSSContext)

        # ✅ Option A invariant:
        # Whatever is in graph_agents is THE node set; do not add extras.
        self._add_nodes(graph, graph_agents)

        entry = pattern.get_entry_point(graph_agents) or graph_agents[0]
        graph.set_entry_point(entry)

        # Conditional wiring if pattern supports it (preserves router registry usage)
        if getattr(pattern, "has_conditional", None) and pattern.has_conditional():
            self._add_conditional_edges(graph, pattern, graph_agents)

        edges = pattern.resolve_edges(graph_agents)
        self._assert_edges_valid(edges, graph_agents, config.pattern_name)

        for e in edges:
            frm = e["from"]
            to = e["to"]
            graph.add_edge(frm, END if str(to).lower() == "end" else to)

        return graph

    def _add_nodes(self, graph: Any, agents_to_run: List[str]) -> None:
        for name in agents_to_run:
            key = str(name).lower()
            if key not in self.node_functions:
                raise GraphBuildError(f"Unknown agent: {name}")
            graph.add_node(key, self.node_functions[key])

    def _add_conditional_edges(self, graph: Any, pattern: GraphPattern, agents: List[str]) -> None:
        """
        Minimal conditional edge wiring using router registry + pattern mappings.
        Safe no-op if pattern doesn't define conditional_edges.
        """
        agents_set = {a.lower() for a in agents}
        conditional = getattr(pattern, "conditional_edges", None) or {}

        for from_node, router_name in conditional.items():
            from_node = (from_node or "").lower()
            if from_node not in agents_set:
                continue

            router_fn = self.routers.get(router_name)

            # Default mapping: END is always allowed
            dest_map: Dict[str, Any] = {"END": END}

            # If pattern exposes destination mappings, respect them
            get_dests = getattr(pattern, "get_conditional_destinations_for", None)
            if callable(get_dests):
                for k, dest in (get_dests(from_node) or {}).items():
                    if not k:
                        continue
                    if isinstance(dest, str) and dest.lower() == "end":
                        dest_map[str(k)] = END
                        continue
                    d = str(dest).lower()
                    if d in agents_set:
                        dest_map[str(k)] = d

            graph.add_conditional_edges(from_node, router_fn, dest_map)

    def _compile_graph(self, graph: StateGraph[OSSSState], config: GraphConfig) -> Any:
        if config.enable_checkpoints and config.memory_manager:
            saver = config.memory_manager.get_memory_saver()
            if saver:
                return graph.compile(checkpointer=saver)
        return graph.compile()

    # ------------------------------------------------------------------
    # CACHE / VALIDATION HELPERS
    # ------------------------------------------------------------------

    def _cache_version(self, pattern_name: str, agents: List[str], checkpoints_enabled: bool) -> str:
        fp = self._patterns_fingerprint()
        ck = "ckpt1" if checkpoints_enabled else "ckpt0"
        agents_key = ",".join([a.lower() for a in agents])
        return f"{pattern_name}:{agents_key}:{ck}:patterns:{fp}"

    def _assert_edges_valid(self, edges: List[Dict[str, str]], agents: List[str], pattern_name: str) -> None:
        agents_set = {a.lower() for a in agents}
        for e in edges:
            frm = str(e.get("from", "")).lower()
            to = str(e.get("to", "")).lower()
            if not frm or not to:
                continue
            if frm != "end" and frm not in agents_set:
                raise GraphBuildError(f"Invalid edge from {frm} in {pattern_name}")
            if to != "end" and to not in agents_set:
                raise GraphBuildError(f"Invalid edge to {to} in {pattern_name}")

    # ------------------------------------------------------------------
    # AGENT VALIDATION UTILITY
    # ------------------------------------------------------------------

    def validate_agents(self, agents: List[str]) -> bool:
        available = set(self.node_functions.keys())
        graph_agents = self._normalize_agents_for_pattern(agents, pattern_name="standard")
        missing = set(graph_agents) - available
        if missing:
            self.logger.error(f"Missing agents: {missing}")
            return False
        return True
