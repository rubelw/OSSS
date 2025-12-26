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

        self.patterns_path = (
            patterns_path
            or os.getenv("OSSS_GRAPH_PATTERNS_PATH")
            or self.DEFAULT_PATTERNS_PATH
        )
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
                "cache_enabled": bool(self.cache),
                "validation_enabled": bool(default_validator),
            },
        )

    # ------------------------------------------------------------------
    # CACHE CONTROL (ADMIN / DEBUG)
    # ------------------------------------------------------------------

    def clear_cache(self) -> None:
        """
        Clear all compiled graph entries from the GraphCache.

        Intended for:
        - hot reloading when graph-patterns.json changes
        - routing / planning logic changes
        - debugging cache behavior
        """
        if not self.cache:
            self.logger.warning(
                "clear_cache called but cache is not initialized",
                extra={"event": "graph_cache_clear_skip"},
            )
            return

        keys_before = self.cache.get_cache_keys()
        self.logger.info(
            "Clearing GraphFactory graph cache",
            extra={
                "event": "graph_cache_clear_all",
                "cached_count": len(keys_before),
                "cached_keys": keys_before,
            },
        )
        self.cache.clear()

    def clear_pattern_cache(self, pattern_name: str, version: Optional[str] = None) -> int:
        """
        Remove cached graphs for a specific pattern.

        - If version is provided, only that version is removed
        - If version is None, all versions for that pattern are removed
        """
        if not self.cache:
            self.logger.warning(
                "clear_pattern_cache called but cache is not initialized",
                extra={"event": "graph_cache_clear_pattern_skip", "pattern_name": pattern_name},
            )
            return 0

        removed = self.cache.remove_pattern(pattern_name, version=version)
        self.logger.info(
            "Pattern cache cleared",
            extra={
                "event": "graph_cache_clear_pattern",
                "pattern_name": pattern_name,
                "version": version,
                "removed": removed,
            },
        )
        return removed

    # ------------------------------------------------------------------
    # PATTERNS
    # ------------------------------------------------------------------

    def _load_patterns(self, path: str) -> None:
        """
        Load graph patterns from JSON.
        """
        self.logger.info(
            "Loading graph patterns",
            extra={"path": path},
        )
        p = pathlib.Path(path)
        if not p.exists():
            self.logger.error(
                "Patterns file not found",
                extra={"path": path},
            )
            raise GraphBuildError(f"Patterns file not found: {path}")
        try:
            self.pattern_registry.load_from_file(str(p))
            self.logger.info(
                "Graph patterns loaded",
                extra={"path": path},
            )
        except Exception as e:
            self.logger.exception(
                "Failed to load graph patterns",
                extra={"path": path, "error": str(e)},
            )
            raise

    def _patterns_fingerprint(self) -> str:
        """
        Fingerprint patterns so cache invalidates when JSON changes.
        Safe if file missing/unreadable.
        """
        try:
            raw = pathlib.Path(self.patterns_path).read_bytes()
            fp = hashlib.sha256(raw).hexdigest()[:16]
            self.logger.debug(
                "Computed patterns fingerprint",
                extra={"fingerprint": fp},
            )
            return fp
        except Exception as e:
            self.logger.warning(
                "Failed to compute patterns fingerprint; using 'nohash'",
                extra={"error": str(e)},
            )
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
        self.logger.info("Registering default routers")

        def refiner_route_query_or_reflect(state: OSSSState) -> str:
            decision = "data_query" if self._should_run_data_query(state) else "reflect"
            self.logger.debug(
                "[router:refiner_route_query_or_reflect] evaluated",
                extra={
                    "decision": decision,
                },
            )
            return decision

        self.routers.register(
            "refiner_route_query_or_reflect", refiner_route_query_or_reflect
        )
        self.logger.info(
            "Default routers registered",
            extra={"routers": ["refiner_route_query_or_reflect"]},
        )

    def _should_run_data_query(self, state: OSSSState) -> bool:
        """
        Determines if data_query should run.

        Matches existing behavior:
        uses execution_state.agent_output_meta._query_profile / query_profile if present.
        """
        self.logger.info(
            "[graph] _should_run_data_query invoked",
            extra={
                "state_type": type(state).__name__,
                "state_keys": list(state.keys()) if isinstance(state, dict) else None,
            },
        )

        try:
            exec_state = state.get("execution_state") if isinstance(state, dict) else None
            if not isinstance(exec_state, dict):
                self.logger.info(
                    "[graph] _should_run_data_query: execution_state missing or not dict; skipping data_query",
                    extra={
                        "execution_state_type": type(exec_state).__name__
                        if exec_state is not None
                        else None,
                        "reason": "execution_state_not_dict_or_missing",
                    },
                )
                return False

            aom = exec_state.get("agent_output_meta")
            if not isinstance(aom, dict):
                self.logger.info(
                    "[graph] _should_run_data_query: agent_output_meta missing or not dict; skipping data_query",
                    extra={
                        "agent_output_meta_type": type(aom).__name__
                        if aom is not None
                        else None,
                        "reason": "agent_output_meta_not_dict_or_missing",
                    },
                )
                return False

            qp = aom.get("_query_profile") or aom.get("query_profile")
            if not isinstance(qp, dict):
                self.logger.info(
                    "[graph] _should_run_data_query: no usable query_profile; skipping data_query",
                    extra={
                        "query_profile_type": type(qp).__name__ if qp is not None else None,
                        "has__query_profile": "_query_profile" in aom,
                        "has_query_profile": "query_profile" in aom,
                        "agent_output_meta_keys": list(aom.keys()),
                        "reason": "query_profile_not_dict_or_missing",
                    },
                )
                return False

            # Extract fields
            intent_raw = qp.get("intent", "")
            action_type_raw = qp.get("action_type", qp.get("action", ""))
            is_query_raw = qp.get("is_query", False)

            intent = str(intent_raw).lower()
            action_type = str(action_type_raw).lower()
            is_query = bool(is_query_raw)

            has_table = bool(qp.get("table"))
            has_tables = bool(qp.get("tables"))
            has_topic = bool(qp.get("topic"))

            self.logger.info(
                "[graph] _should_run_data_query: extracted query_profile fields",
                extra={
                    "intent": intent,
                    "intent_raw": intent_raw,
                    "action_type": action_type,
                    "action_type_raw": action_type_raw,
                    "is_query_flag": is_query,
                    "has_table": has_table,
                    "has_tables": has_tables,
                    "has_topic": has_topic,
                    "query_profile_keys": list(qp.keys()),
                },
            )

            # Decision logic (unchanged; just with explicit logs)

            if intent != "action":
                self.logger.info(
                    "[graph] _should_run_data_query: NOT running data_query (intent != 'action')",
                    extra={
                        "intent": intent,
                        "reason": "intent_not_action",
                    },
                )
                return False

            if action_type == "query":
                self.logger.info(
                    "[graph] _should_run_data_query: running data_query (action_type == 'query')",
                    extra={
                        "intent": intent,
                        "action_type": action_type,
                        "is_query_flag": is_query,
                        "reason": "action_type_query",
                    },
                )
                return True

            if is_query:
                self.logger.info(
                    "[graph] _should_run_data_query: running data_query (is_query flag true)",
                    extra={
                        "intent": intent,
                        "action_type": action_type,
                        "is_query_flag": is_query,
                        "reason": "is_query_flag_true",
                    },
                )
                return True

            if has_table or has_tables or has_topic:
                self.logger.info(
                    "[graph] _should_run_data_query: running data_query (table/tables/topic present)",
                    extra={
                        "intent": intent,
                        "action_type": action_type,
                        "is_query_flag": is_query,
                        "has_table": has_table,
                        "has_tables": has_tables,
                        "has_topic": has_topic,
                        "reason": "schema_hints_present",
                    },
                )
                return True

            self.logger.info(
                "[graph] _should_run_data_query: NOT running data_query (no query signals matched)",
                extra={
                    "intent": intent,
                    "action_type": action_type,
                    "is_query_flag": is_query,
                    "has_table": has_table,
                    "has_tables": has_tables,
                    "has_topic": has_topic,
                    "reason": "no_match",
                },
            )
            return False

        except Exception as e:
            self.logger.exception(
                "[graph] _should_run_data_query: exception while evaluating; defaulting to False",
                extra={"error": str(e)},
            )
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
            self.logger.debug(
                "execution_config missing or not dict; initializing new dict",
                extra={"prev_type": type(ec).__name__ if ec is not None else None},
            )
            ec = {}
            exec_state["execution_config"] = ec
        else:
            self.logger.debug(
                "execution_config found",
                extra={"keys": list(ec.keys())},
            )
        return ec

    def _apply_option_a_planning_bridge(self, cfg: GraphConfig) -> GraphConfig:
        """
        Option A bridge:
          - call apply_option_a_fastpath_planning BEFORE compilation
          - adopt exec_state.execution_config.graph_pattern into cfg.pattern_name
          - adopt exec_state.planned_agents into cfg.agents_to_run (authoritative)
        """
        self.logger.info(
            "[OptionA] Applying planning bridge",
            extra={
                "pattern_name_before": cfg.pattern_name,
                "agents_before": cfg.agents_to_run,
            },
        )
        exec_state = cfg.execution_state
        if not isinstance(exec_state, dict):
            self.logger.debug(
                "[OptionA] execution_state missing or not dict; skipping planning bridge",
                extra={
                    "exec_state_type": type(exec_state).__name__
                    if exec_state is not None
                    else None
                },
            )
            return cfg

        chosen_target = cfg.chosen_target or exec_state.get("route")
        if not isinstance(chosen_target, str):
            chosen_target = ""

        self.logger.debug(
            "[OptionA] Running fastpath planning",
            extra={"chosen_target": chosen_target or "refiner"},
        )

        # ✅ Option A: decide pattern + planned agents BEFORE compilation
        apply_option_a_fastpath_planning(
            exec_state=exec_state, chosen_target=chosen_target or "refiner"
        )

        ec = self._ensure_execution_config(exec_state)

        # ✅ SPECIAL HANDLING for refiner_final
        # We only apply this branch when the effective graph_pattern is "refiner_final".
        # That means we're in the "Option A" fastpath where the graph is:
        #   refiner -> (maybe data_query) -> final
        if ec.get("graph_pattern") == "refiner_final":

            raw_query = str(
                exec_state.get("query")
                or exec_state.get("user_query")
                or exec_state.get("raw_query")
                or ""
            ).lower()


            has_database_kw = "database" in raw_query.lower()
            has_query_kw = "query" in raw_query.lower()
            request_has_db_or_query = has_database_kw or has_query_kw

            if bool(raw_query) and not request_has_db_or_query:

                planned: List[str] = ["refiner"]
                planned.append("final")

                exec_state["planned_agents"] = planned
                self.logger.info(
                    "[OptionA] refiner_final: no query_profile present; using raw-query heuristic",
                    extra={
                        "planned_agents": planned,
                        "reason": "no_query_profile",
                        "run_data_query": False,
                        "raw_query_len": len(raw_query),
                        "raw_query_has_database": has_database_kw,
                        "raw_query_has_query": has_query_kw,
                    },
                )
            else:

                # NEW: gate on raw request text only, per your requirement
                request_has_db_or_query = has_database_kw or has_query_kw

                planned: List[str] = ["refiner"]
                planned.append("data_query")
                planned.append("final")

                exec_state["planned_agents"] = planned
                self.logger.info(
                    "[OptionA] planned_agents set for refiner_final",
                    extra={
                        "planned_agents": planned,
                        "run_data_query": True,
                        "intent_is_action": "action",
                        "request_has_db_or_query": request_has_db_or_query,
                    },
                )

        # ✅ If caller didn’t pass pattern_name, adopt computed graph_pattern
        gp = ec.get("graph_pattern")
        if isinstance(gp, str) and gp:
            self.logger.debug(
                "[OptionA] Overriding pattern_name from execution_config",
                extra={
                    "pattern_name_before": cfg.pattern_name,
                    "pattern_name_after": gp,
                },
            )
            cfg = replace(cfg, pattern_name=gp)

        # ✅ planned_agents is authoritative for which nodes exist
        planned = exec_state.get("planned_agents")
        if isinstance(planned, list) and planned:
            self.logger.info(
                "[OptionA] Using planned_agents as authoritative node set",
                extra={"planned_agents": planned},
            )
            cfg = replace(cfg, agents_to_run=[str(a).lower() for a in planned if a])

        self.logger.info(
            "[OptionA] Planning bridge complete",
            extra={
                "pattern_name_after": cfg.pattern_name,
                "agents_after": cfg.agents_to_run,
            },
        )
        return cfg

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def create_graph(self, config: GraphConfig) -> Any:
        self.logger.info(
            "create_graph called",
            extra={
                "pattern_name_initial": config.pattern_name,
                "agents_initial": config.agents_to_run,
                "enable_checkpoints": config.enable_checkpoints,
                "cache_enabled": config.cache_enabled,
                "enable_validation": config.enable_validation,
            },
        )
        try:
            # 🔑 Option A order:
            #   1) apply planning bridge (may change pattern + planned agents)
            #   2) normalize agents for selected pattern (still enforces invariants)
            config = self._apply_option_a_planning_bridge(config)
            config = self.prepare_config(config)

            graph_agents = list(config.agents_to_run or [])
            self.logger.info(
                "Graph config prepared",
                extra={
                    "pattern_name": config.pattern_name,
                    "graph_agents": graph_agents,
                },
            )

            pattern = self.pattern_registry.get(config.pattern_name)
            if not pattern:
                self.logger.error(
                    "Unknown graph pattern",
                    extra={"pattern_name": config.pattern_name},
                )
                raise GraphBuildError(f"Unknown graph pattern: {config.pattern_name}")

            # Optional semantic validation BEFORE graph creation (preserved)
            if config.enable_validation:
                validator = config.validator or self.default_validator
                if validator:
                    self.logger.info(
                        "Running workflow semantic validation",
                        extra={
                            "pattern_name": config.pattern_name,
                            "graph_agents": graph_agents,
                            "strict_mode": config.validation_strict_mode,
                        },
                    )
                    result = validator.validate_workflow(
                        agents=graph_agents,
                        pattern=config.pattern_name,
                        strict_mode=config.validation_strict_mode,
                    )
                    if result.has_errors:
                        summary = "; ".join(result.error_messages)
                        self.logger.error(
                            "Workflow validation failed",
                            extra={"errors": result.error_messages},
                        )
                        raise ValidationError(
                            f"Workflow validation failed: {summary}", result
                        )
                else:
                    self.logger.warning(
                        "Validation enabled but no validator available",
                    )

            cache_version = self._cache_version(
                config.pattern_name, graph_agents, config.enable_checkpoints
            )

            if config.cache_enabled:
                self.logger.debug(
                    "Checking graph cache",
                    extra={
                        "pattern_name": config.pattern_name,
                        "agents": graph_agents,
                        "cache_version": cache_version,
                    },
                )
                cached = self.cache.get_cached_graph(
                    pattern_name=config.pattern_name,
                    agents=graph_agents,
                    checkpoints_enabled=config.enable_checkpoints,
                    version=cache_version,
                )
                if cached:
                    self.logger.info(
                        "Using cached compiled graph",
                        extra={
                            "pattern_name": config.pattern_name,
                            "agents": graph_agents,
                            "cache_version": cache_version,
                        },
                    )
                    return cached

            self.logger.info(
                "Creating new StateGraph",
                extra={
                    "pattern_name": config.pattern_name,
                    "agents": graph_agents,
                },
            )
            graph = self._create_state_graph(config, pattern, graph_agents)
            compiled = self._compile_graph(graph, config)

            if config.cache_enabled:
                self.logger.info(
                    "Caching compiled graph",
                    extra={
                        "pattern_name": config.pattern_name,
                        "agents": graph_agents,
                        "cache_version": cache_version,
                    },
                )
                self.cache.cache_graph(
                    pattern_name=config.pattern_name,
                    agents=graph_agents,
                    checkpoints_enabled=config.enable_checkpoints,
                    compiled_graph=compiled,
                    version=cache_version,
                )

            self.logger.info(
                "Graph compilation complete",
                extra={
                    "pattern_name": config.pattern_name,
                    "agents": graph_agents,
                },
            )
            return compiled

        except ValidationError:
            # Already logged above; just re-raise
            raise
        except Exception as e:
            self.logger.exception(
                "Failed to create graph",
                extra={"error": str(e)},
            )
            raise GraphBuildError(f"Failed to create graph: {e}") from e

    # ------------------------------------------------------------------
    # NORMALIZATION (PATTERN-AWARE)
    # ------------------------------------------------------------------

    def _is_terminal_output_pattern(self, pattern_name: str) -> bool:
        value = pattern_name.lower() in {
            "refiner_final",
            "refiner_only_output",
            "minimal",
        }
        self.logger.debug(
            "_is_terminal_output_pattern evaluated",
            extra={"pattern_name": pattern_name, "is_terminal": value},
        )
        return value

    def _normalize_agents_for_pattern(
        self, agents: Iterable[str], pattern_name: str
    ) -> List[str]:
        self.logger.debug(
            "Normalizing agents for pattern",
            extra={
                "pattern_name": pattern_name,
                "agents_raw": list(agents or []),
            },
        )

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

        self.logger.debug(
            "Agents normalized for pattern",
            extra={
                "pattern_name": pattern_name,
                "agents_normalized": out,
            },
        )
        return out

    def prepare_config(self, cfg: GraphConfig) -> GraphConfig:
        self.logger.debug(
            "Preparing GraphConfig via normalization",
            extra={
                "pattern_name": cfg.pattern_name,
                "agents_before": cfg.agents_to_run,
            },
        )
        deduped = self._normalize_agents_for_pattern(
            cfg.agents_to_run, cfg.pattern_name
        )

        if deduped == list(cfg.agents_to_run or []):
            self.logger.debug(
                "GraphConfig agents unchanged after normalization",
                extra={"agents": deduped},
            )
            return cfg

        self.logger.info(
            "GraphConfig agents updated after normalization",
            extra={
                "pattern_name": cfg.pattern_name,
                "agents_before": cfg.agents_to_run,
                "agents_after": deduped,
            },
        )
        return replace(cfg, agents_to_run=deduped)

    # ------------------------------------------------------------------
    # GRAPH BUILDING
    # ------------------------------------------------------------------

    def _create_state_graph(
            self,
            config: GraphConfig,
            pattern: GraphPattern,
            graph_agents: List[str],
    ) -> Any:
        """
        Build the underlying LangGraph StateGraph.

        IMPORTANT:
        - graph_agents is already the authoritative node set (Option A)
        - For terminal patterns (e.g. refiner_final), we may need to
          rewrite edges if extra nodes like data_query are present.
        """
        self.logger.info(
            "Creating new StateGraph",
            extra={
                "pattern_name": config.pattern_name,
                "agents": graph_agents,
            },
        )

        graph = StateGraph[OSSSState](state_schema=OSSSState, context_schema=OSSSContext)

        self.logger.info(
            "Creating StateGraph structure",
            extra={
                "pattern_name": config.pattern_name,
                "agents": graph_agents,
            },
        )

        # ---- Nodes ----------------------------------------------------
        self._add_nodes(graph, graph_agents)

        entry = pattern.get_entry_point(graph_agents) or graph_agents[0]
        self.logger.info(
            "Setting graph entry point",
            extra={"entry_point": entry},
        )
        graph.set_entry_point(entry)

        # ---- Conditional edges (if any) ------------------------------
        if getattr(pattern, "has_conditional", None) and pattern.has_conditional():
            self.logger.info(
                "Adding conditional edges via router registry",
                extra={
                    "pattern_name": config.pattern_name,
                    "agents": graph_agents,
                },
            )
            self._add_conditional_edges(graph, pattern, graph_agents)

        # ---- Base edges from pattern ---------------------------------
        edges: List[Dict[str, str]] = pattern.resolve_edges(graph_agents) or []
        self.logger.info(
            "Pattern resolved edges",
            extra={
                "pattern_name": config.pattern_name,
                "raw_edges": edges,
            },
        )

        # ---- SPECIAL CASE: refiner_final + data_query ----------------
        # In this pattern, the JSON spec likely only describes:
        #   refiner -> final
        # To actually run data_query when it is present in graph_agents,
        # we rewrite that edge to:
        #   refiner -> data_query -> final
        lowered_agents = [a.lower() for a in graph_agents]
        if config.pattern_name.lower() == "refiner_final" and "data_query" in lowered_agents:
            self.logger.info(
                "[OptionA] Rewriting edges for refiner_final with data_query present",
                extra={"edges_before": edges},
            )
            new_edges: List[Dict[str, str]] = []
            for e in edges:
                frm = str(e.get("from", "")).lower()
                to = str(e.get("to", "")).lower()

                # Replace refiner->final / refiner->END with a hop through data_query
                if frm == "refiner" and to in {"final", "end"}:
                    new_edges.append({"from": "refiner", "to": "data_query"})
                    new_edges.append({"from": "data_query", "to": to})
                else:
                    new_edges.append(e)

            edges = new_edges
            self.logger.info(
                "[OptionA] Edges after rewrite for refiner_final with data_query",
                extra={"edges_after": edges},
            )

        # ---- Validate & register edges -------------------------------
        self._assert_edges_valid(edges, graph_agents, config.pattern_name)

        for e in edges:
            frm = e["from"]
            to = e["to"]
            dest = END if str(to).lower() == "end" else to
            self.logger.info(
                "Adding edge to graph",
                extra={"from": frm, "to": to},
            )
            graph.add_edge(frm, dest)

        self.logger.info(
            "StateGraph structure created",
            extra={
                "pattern_name": config.pattern_name,
                "agents": graph_agents,
            },
        )

        return graph

    def _add_nodes(self, graph: Any, agents_to_run: List[str]) -> None:
        self.logger.info(
            "Adding nodes to graph",
            extra={"agents_to_run": agents_to_run},
        )
        for name in agents_to_run:
            key = str(name).lower()
            if key not in self.node_functions:
                self.logger.error(
                    "Unknown agent when adding nodes",
                    extra={"agent": name},
                )
                raise GraphBuildError(f"Unknown agent: {name}")
            self.logger.debug(
                "Adding node",
                extra={"agent": key},
            )
            graph.add_node(key, self.node_functions[key])

    def _add_conditional_edges(
        self, graph: Any, pattern: GraphPattern, agents: List[str]
    ) -> None:
        """
        Minimal conditional edge wiring using router registry + pattern mappings.
        Safe no-op if pattern doesn't define conditional_edges.
        """
        self.logger.info(
            "Adding conditional edges",
            extra={"agents": agents},
        )
        agents_set = {a.lower() for a in agents}
        conditional = getattr(pattern, "conditional_edges", None) or {}

        for from_node, router_name in conditional.items():
            from_node = (from_node or "").lower()
            if from_node not in agents_set:
                self.logger.debug(
                    "Skipping conditional edge for node not in agents",
                    extra={"from_node": from_node},
                )
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

            self.logger.debug(
                "Registering conditional edges",
                extra={
                    "from_node": from_node,
                    "router": router_name,
                    "destinations": list(dest_map.keys()),
                },
            )
            graph.add_conditional_edges(from_node, router_fn, dest_map)

    def _compile_graph(self, graph: StateGraph[OSSSState], config: GraphConfig) -> Any:
        self.logger.info(
            "Compiling graph",
            extra={
                "enable_checkpoints": config.enable_checkpoints,
                "has_memory_manager": bool(config.memory_manager),
            },
        )
        if config.enable_checkpoints and config.memory_manager:
            saver = config.memory_manager.get_memory_saver()
            if saver:
                self.logger.debug("Compiling graph with checkpointer")
                return graph.compile(checkpointer=saver)
            else:
                self.logger.warning(
                    "Checkpoints enabled but memory_saver is None; compiling without checkpointer"
                )
        self.logger.debug("Compiling graph without checkpointer")
        return graph.compile()

    # ------------------------------------------------------------------
    # CACHE / VALIDATION HELPERS
    # ------------------------------------------------------------------

    def _cache_version(
        self, pattern_name: str, agents: List[str], checkpoints_enabled: bool
    ) -> str:
        fp = self._patterns_fingerprint()
        ck = "ckpt1" if checkpoints_enabled else "ckpt0"
        agents_key = ",".join([a.lower() for a in agents])
        version = f"{pattern_name}:{agents_key}:{ck}:patterns:{fp}"
        self.logger.debug(
            "Computed cache version",
            extra={
                "pattern_name": pattern_name,
                "agents": agents,
                "checkpoints_enabled": checkpoints_enabled,
                "version": version,
            },
        )
        return version

    def _assert_edges_valid(
        self, edges: List[Dict[str, str]], agents: List[str], pattern_name: str
    ) -> None:
        self.logger.debug(
            "Validating edges against agents",
            extra={
                "pattern_name": pattern_name,
                "edges_count": len(edges),
                "agents": agents,
            },
        )
        agents_set = {a.lower() for a in agents}
        for e in edges:
            frm = str(e.get("from", "")).lower()
            to = str(e.get("to", "")).lower()
            if not frm or not to:
                self.logger.debug(
                    "Skipping edge with missing from/to",
                    extra={"edge": e},
                )
                continue
            if frm != "end" and frm not in agents_set:
                self.logger.error(
                    "Invalid edge: from-node not in agents",
                    extra={"from": frm, "pattern_name": pattern_name},
                )
                raise GraphBuildError(f"Invalid edge from {frm} in {pattern_name}")
            if to != "end" and to not in agents_set:
                self.logger.error(
                    "Invalid edge: to-node not in agents",
                    extra={"to": to, "pattern_name": pattern_name},
                )
                raise GraphBuildError(f"Invalid edge to {to} in {pattern_name}")

    # ------------------------------------------------------------------
    # AGENT VALIDATION UTILITY
    # ------------------------------------------------------------------

    def validate_agents(self, agents: List[str]) -> bool:
        self.logger.info(
            "Validating requested agents",
            extra={"requested_agents": agents},
        )
        available = set(self.node_functions.keys())
        graph_agents = self._normalize_agents_for_pattern(
            agents, pattern_name="standard"
        )
        missing = set(graph_agents) - available
        if missing:
            self.logger.error(
                "Missing agents detected during validation",
                extra={"missing_agents": list(missing)},
            )
            return False
        self.logger.info(
            "Agents validated successfully",
            extra={"normalized_agents": graph_agents},
        )
        return True
