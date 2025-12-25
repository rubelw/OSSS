"""
Production LangGraph orchestrator for OSSS agents.

UPDATED to use:
- Config-driven graph patterns (graph-patterns.json)
- Router registry (orchestration/routers.py)
- GraphFactory that loads patterns dynamically and applies conditional routing
  via add_conditional_edges using router names from the pattern spec.

Key behavior:
- Default pattern is "standard" (refiner → critic/historian → synthesis)
- Pattern can be changed per-request via config["execution_config"]["graph_pattern"]
  (or config["graph_pattern"] fallback).
- Agent selection (which nodes exist) is still controlled by routing/optimizer,
  but *edges* come from the selected pattern.
"""

import time
import uuid
import os
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from OSSS.ai.context import AgentContext
from OSSS.ai.agents.base_agent import BaseAgent
from OSSS.ai.agents.registry import get_agent_registry
from OSSS.ai.observability import get_logger
from OSSS.ai.correlation import (
    ensure_correlation_context,
    create_child_span,
    add_trace_metadata,
    CorrelationContext,
    context_correlation_id,
    context_workflow_id,
    context_trace_metadata,
)
from OSSS.ai.events import (
    emit_workflow_completed,
    emit_routing_decision_from_object,
)
from OSSS.ai.orchestration.state_bridge import AgentContextStateBridge
from OSSS.ai.orchestration.state_schemas import (
    OSSSState,
    OSSSContext,
    RefinerState,
    CriticState,
    HistorianState,
    SynthesisState,
    FinalState,
    create_initial_state,
    validate_state_integrity,
)
from OSSS.ai.orchestration.node_wrappers import (
    NodeExecutionError,
    get_node_dependencies,
)

from OSSS.ai.orchestration.routing import (
    DBQueryRouter,              # ✅ pre-route before compile
    planned_agents_for_route_key,
)

from OSSS.ai.orchestration.memory_manager import (
    OSSSMemoryManager,
    create_memory_manager,
)

# ✅ New pattern/routers wiring
from OSSS.ai.orchestration.routers import build_default_router_registry

# ✅ GraphFactory now assumed to load patterns/spec + json patterns
from OSSS.ai.orchestration.graph_factory import (
    GraphFactory,
    GraphBuildError,
    GraphConfig,
)

from .graph_cache import GraphCache, CacheConfig

# Existing (optional) enhanced routing/optimizer
from OSSS.ai.routing import (
    ResourceOptimizer,
    ResourceConstraints,
    OptimizationStrategy,
    RoutingDecision,
)

from OSSS.ai.rag.additional_index_rag import (
    rag_prefetch_additional,
    RagResult,
    RagHit,
)

from OSSS.ai.agents.metadata import AgentMetadata

from OSSS.ai.orchestration.nodes.decision_node import DecisionNode, DecisionCriteria
from OSSS.ai.orchestration.nodes.base_advanced_node import NodeExecutionContext



logger = get_logger(__name__)

DEFAULT_RAG_JSONL_PATH = os.getenv(
    "OSSS_RAG_JSONL_PATH",
    "/workspace/vector_indexes/main/embeddings.jsonl",
)

def normalize_agents(agents: list[str], *, pattern_name: str = "standard") -> list[str]:
    a = [str(x).lower() for x in (agents or []) if x]

    if "refiner" not in a:
        a.insert(0, "refiner")

    # ✅ only force final on patterns that require it
    if pattern_name.strip() not in ("refiner_final", "refiner-only", "refiner_only"):
        if "final" not in a:
            a.append("final")

    if "data_query" in a:
        a = [x for x in a if x not in ( "historian")]

    out: list[str] = []
    seen = set()
    for x in a:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

def _canonical_execution_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Option A step (4): produce a single deterministic execution_config dict.

    Supports both shapes:
      A) nested:  config["execution_config"] = {...}
      B) flat:    config["use_rag"]=..., config["top_k"]=..., etc.

    Returns a dict that agents can rely on:
      - rag settings under rag.enabled/top_k when present
      - final_llm settings preserved if provided
    """
    if not isinstance(config, dict):
        return {}

    # Start with nested execution_config if present
    base: Dict[str, Any] = {}
    nested = config.get("execution_config")
    if isinstance(nested, dict):
        base.update(nested)

    # Merge common flattened knobs into base if they exist
    for k in ("parallel_execution", "timeout_seconds", "use_llm_intent", "use_rag", "top_k", "graph_pattern"):
        if k in config and k not in base:
            base[k] = config[k]

    # -------------------------
    # RAG normalization (unchanged)
    # -------------------------
    rag = base.get("rag")
    if not isinstance(rag, dict):
        rag = {}

    if "use_rag" in base and "enabled" not in rag:
        rag["enabled"] = bool(base.get("use_rag"))
    if "top_k" in base and "top_k" not in rag:
        try:
            rag["top_k"] = int(base.get("top_k"))
        except Exception:
            pass

    # ✅ NEW: default JSONL path for RAG if enabled
    if rag.get("enabled") and not rag.get("jsonl_path"):
        rag["jsonl_path"] = DEFAULT_RAG_JSONL_PATH


    if rag:
        base["rag"] = rag

    # -------------------------
    # ✅ final_llm normalization + env fallback
    # -------------------------
    final_llm = base.get("final_llm")
    if isinstance(final_llm, dict):
        provider = str(final_llm.get("provider", "")).lower()
        # Only care about base_url if we're using the gateway provider
        if provider == "gateway" and not final_llm.get("base_url"):
            env_base = os.getenv("OSSS_AI_GATEWAY_BASE_URL")
            if env_base:
                final_llm["base_url"] = env_base
        base["final_llm"] = final_llm

    return base



def _ensure_effective_queries(state: Dict[str, Any], base_query: str) -> None:
    """
    Ensure execution_state.effective_queries exists for the run.

    Node wrappers will overwrite per-agent values right before each agent runs:
      execution_state["effective_queries"][agent_name] = effective_query
    """
    exec_state = state.setdefault("execution_state", {})
    if not isinstance(exec_state, dict):
        state["execution_state"] = {}
        exec_state = state["execution_state"]

    effective = exec_state.setdefault("effective_queries", {})
    if not isinstance(effective, dict):
        exec_state["effective_queries"] = {}
        effective = exec_state["effective_queries"]

    effective.setdefault("user", base_query)


@dataclass
class RagIndexConfig:
    """
    Config for a single RAG index.

    Values here are *defaults* that can be overridden per-request via exec_cfg["rag"].
    """
    name: str = "main"
    default_top_k: int = 6
    max_snippet_chars: int = 6000


@dataclass
class RagSettings:
    """
    Global RAG settings: per-index configs.
    """
    indexes: Dict[str, RagIndexConfig]


# Instantiate with some sane defaults; you can extend this as needed.
RAG_SETTINGS = RagSettings(
    indexes={
        "main": RagIndexConfig(
            name="main",
            default_top_k=6,
            max_snippet_chars=6000,
        ),
        "tutor": RagIndexConfig(
            name="tutor",
            default_top_k=4,
            max_snippet_chars=4000,
        ),
        "agent": RagIndexConfig(
            name="agent",
            default_top_k=3,
            max_snippet_chars=3000,
        ),
    }
)


def _resolve_rag_config(
        raw_index_name: str,
        rag_cfg: Dict[str, Any],
) -> tuple[str, int, int]:
    """
    Given the requested index name and per-request rag_cfg, return:
        (effective_index_name, top_k, snippet_max_chars)

    Priority:
    - rag_cfg overrides (top_k, snippet_max_chars, index)
    - then RAG_SETTINGS per-index defaults
    - then hard-coded fallbacks
    """
    base_cfg = RAG_SETTINGS.indexes.get(
        raw_index_name,
        RagIndexConfig(name=raw_index_name),  # fallback config
    )

    # index name can be overridden in rag_cfg (e.g., alias)
    effective_index = str(rag_cfg.get("index", base_cfg.name))

    # top_k: per-request override > per-index default > hard default
    top_k = int(rag_cfg.get("top_k", base_cfg.default_top_k or 5))

    # snippet_max_chars: per-request override > per-index default > hard default
    snippet_max_chars = int(
        rag_cfg.get("snippet_max_chars", base_cfg.max_snippet_chars or 6000)
    )

    return effective_index, top_k, snippet_max_chars


class LangGraphOrchestrator:
    """
    Production LangGraph orchestrator for OSSS agents.

    Major responsibilities:
    - Decide which agents to include for a run (agent selection)
    - Build/compile a LangGraph graph using GraphFactory (pattern-driven edges)
    - Execute the compiled graph and return an AgentContext
    """

    DEFAULT_PATTERN = "standard"

    def __init__(
        self,
        agents_to_run: Optional[List[str]] = None,
        enable_checkpoints: bool = False,
        thread_id: Optional[str] = None,
        memory_manager: Optional[OSSSMemoryManager] = None,
        use_enhanced_routing: bool = True,
        optimization_strategy: OptimizationStrategy = OptimizationStrategy.BALANCED,
        graph_pattern: Optional[str] = None,
    ) -> None:
        # Default agents: includes data_query, but the *standard pattern* does not require it.
        self.default_agents = ["refiner", "data_query", "historian", "final"]

        self._compiled_graph = None
        self._compiled_graph_key: Optional[tuple[str, tuple[str, ...], bool]] = None

        self.use_enhanced_routing = use_enhanced_routing
        self.optimization_strategy = optimization_strategy

        self.resource_optimizer: Optional[ResourceOptimizer] = (
            ResourceOptimizer() if self.use_enhanced_routing else None
        )

        self.agents_to_run = agents_to_run or self.default_agents
        self.enable_checkpoints = enable_checkpoints
        self.thread_id = thread_id
        self.registry = get_agent_registry()
        self.logger = get_logger(f"{__name__}.LangGraphOrchestrator")

        # ✅ pattern is now a first-class knob
        self.graph_pattern = (graph_pattern or self.DEFAULT_PATTERN).strip()

        # Memory manager
        self.memory_manager = memory_manager or create_memory_manager(
            enable_checkpoints=enable_checkpoints,
            thread_id=thread_id,
        )

        # Compatibility / health checks
        self.agents: List[BaseAgent] = []

        # Performance stats
        self.total_executions = 0
        self.successful_executions = 0
        self.failed_executions = 0

        self.state_bridge = AgentContextStateBridge()

        # -----------------------------------------------------------------
        # ✅ DecisionNode (single instance, used per-request)
        # -----------------------------------------------------------------
        decision_metadata = AgentMetadata(
            name="router_decision",
            agent_class=DecisionNode.__name__,  # ✅ required
            execution_pattern="decision",
        )

        # Example criterion: prefer "action" when refiner/intents indicate query/action
        def _is_actionish(ctx: NodeExecutionContext) -> float:
            es = getattr(ctx, "execution_state", None) or {}
            # ✅ If DBQueryRouter already marked this as action, treat it as 1.0
            if str(es.get("route_key", "")).lower() == "action":
                return 1.0

            aom = (es.get("agent_output_meta") or {}) if isinstance(es, dict) else {}
            qp = aom.get("_query_profile") or aom.get("query_profile") or {}
            if not isinstance(qp, dict):
                return 0.0
            intent = str(qp.get("intent", "")).lower()
            action_type = str(qp.get("action_type", qp.get("action", ""))).lower()
            return 1.0 if (intent == "action" and action_type == "query") else 0.0

        self.decision_node = DecisionNode(
            metadata=decision_metadata,
            node_name="router_decision",
            decision_criteria=[
                DecisionCriteria(
                    name="action_query_intent",
                    evaluator=_is_actionish,
                    weight=1.0,
                    threshold=0.5,
                )
            ],
            paths={
                "action": ["refiner", "data_query", "final"],
                "reflect": ["refiner", "historian", "final"],
            },
        )

        # ✅ GraphFactory: pass router registry so conditional routing works via named routers
        cache_config = CacheConfig(max_size=10, ttl_seconds=1800)
        router_registry = build_default_router_registry()
        self.graph_factory = GraphFactory(
            cache_config=cache_config,
            router_registry=router_registry,  # <-- NEW (GraphFactory should accept this)
        )

        self._graph = None
        self._compiled_graph = None

        self.logger.info(
            "Initialized LangGraphOrchestrator",
            extra={
                "agents": self.agents_to_run,
                "pattern": self.graph_pattern,
                "checkpoints": self.enable_checkpoints,
                "thread_id": self.thread_id,
                "enhanced_routing": self.use_enhanced_routing,
                "optimization_strategy": self.optimization_strategy.value,
            },
        )

    # inside LangGraphOrchestrator

    async def _prefetch_rag(
            self,
            *,
            query: str,
            state: Dict[str, Any],
    ) -> None:
        # Ensure we have execution_state
        exec_state = state.setdefault("execution_state", {})

        # Ensure we have execution_config
        exec_cfg = exec_state.get("execution_config")
        if not isinstance(exec_cfg, dict):
            exec_cfg = {}
            exec_state["execution_config"] = exec_cfg

        rag_cfg = exec_cfg.get("rag") or {}
        if not isinstance(rag_cfg, dict) or not rag_cfg.get("enabled"):
            self.logger.info("[orchestrator] RAG disabled for this request; skipping prefetch")
            exec_state["rag_enabled"] = False
            # Mirror to top level for consumers that only look at state
            state["rag_enabled"] = False
            state.pop("rag_context", None)
            state.pop("rag_snippet", None)
            state.pop("rag_hits", None)
            return

        # ---- RAG mode: hard_fail | soft_disable | partial ----
        rag_mode = str(rag_cfg.get("mode") or os.getenv("OSSS_RAG_MODE", "soft_disable")).lower()
        if rag_mode not in {"hard_fail", "soft_disable", "partial"}:
            rag_mode = "soft_disable"

        # Locals we *might* reuse in partial mode
        rag_context_str: str = ""
        rag_hits: list[dict] = []
        rag_snippet: str = ""
        snippet_max_chars: int = int(rag_cfg.get("snippet_max_chars", 6000))

        try:
            # ---- Resolve index-level config (defaults + overrides) ----
            raw_index_name = str(rag_cfg.get("index", "main"))
            index_name, top_k, snippet_max_chars = _resolve_rag_config(
                raw_index_name=raw_index_name,
                rag_cfg=rag_cfg,
            )

            # Per-request extras still read directly from rag_cfg
            embed_model = rag_cfg.get("embed_model", "nomic-embed-text")
            jsonl_path = rag_cfg.get("jsonl_path", DEFAULT_RAG_JSONL_PATH)

            # ---- Call helper that now returns RagResult ----
            rag_result: RagResult = await rag_prefetch_additional(
                query=query,
                index=index_name,
                top_k=top_k,
            )

            # Combined prompt-ready context
            rag_context_str = rag_result.combined_text or ""

            # Convert RagHit objects into JSON-serializable dicts for state
            rag_hits = []
            for hit in rag_result.hits:
                chunk = hit.chunk
                rag_hits.append(
                    {
                        "id": getattr(chunk, "id", None),
                        "index": rag_result.meta.get("index", index_name),
                        "score": float(hit.score),
                        "source": getattr(chunk, "source", None),
                        "filename": getattr(chunk, "filename", None),
                        "chunk_index": getattr(chunk, "chunk_index", None),
                        "text": getattr(chunk, "text", None),
                    }
                )

            # Compute snippet using resolved config
            rag_snippet = rag_context_str[:snippet_max_chars] if rag_context_str else ""

            # ---- Store into exec_state (internal) ----
            exec_state["rag_enabled"] = True
            exec_state["rag_context"] = rag_context_str
            exec_state["rag_snippet"] = rag_snippet
            exec_state["rag_hits"] = rag_hits

            # Merge helper's meta with orchestrator meta
            rag_meta = {
                "provider": "ollama",
                "embed_model": embed_model,
                "jsonl_path": jsonl_path,
                "top_k": top_k,
                "index": index_name,
                "hits_count": len(rag_hits),
            }
            rag_meta.update(rag_result.meta or {})
            exec_state["rag_meta"] = rag_meta

            # 🔴 Critical bridge for Final node and other consumers:
            state["rag_enabled"] = True
            state["rag_context"] = rag_context_str
            state["rag_snippet"] = rag_snippet
            state["rag_hits"] = rag_hits

            self.logger.info(
                "[orchestrator] RAG context stored",
                extra={
                    "rag_chars": len(rag_context_str),
                    "hits_count": len(rag_hits),
                    "index": index_name,
                    "top_k": top_k,
                    "snippet_max_chars": snippet_max_chars,
                    "rag_mode": rag_mode,
                },
            )

        except Exception as e:
            # Decide behavior based on rag_mode
            self.logger.warning(
                f"[orchestrator] RAG prefetch failed (rag_mode={rag_mode}): {e}",
                extra={"rag_mode": rag_mode},
            )

            if rag_mode == "hard_fail":
                # Mark error, but *fail* the request so caller sees it
                exec_state["rag_enabled"] = False
                exec_state["rag_error"] = str(e)

                state["rag_enabled"] = False
                state["rag_error"] = str(e)
                # Let the exception bubble
                raise

            if rag_mode == "partial" and (rag_context_str or rag_hits):
                # Keep whatever we managed to get; mark it as partial
                exec_state["rag_enabled"] = True
                exec_state["rag_partial"] = True
                exec_state["rag_error"] = str(e)

                state["rag_enabled"] = True
                state["rag_partial"] = True
                # context/snippet/hits stay as-is in state/exec_state
                return

            # Default: soft_disable (current behavior)
            exec_state["rag_enabled"] = False
            exec_state["rag_error"] = str(e)

            state["rag_enabled"] = False
            state["rag_error"] = str(e)
            state.pop("rag_context", None)
            state.pop("rag_snippet", None)
            state.pop("rag_hits", None)

    # ---------------------------------------------------------------------
    # Agent list resolution
    # ---------------------------------------------------------------------

    def _get_classifier_prestep(self, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(config, dict):
            return None

        prestep = config.get("prestep")
        if isinstance(prestep, dict):
            cls = prestep.get("classifier")
            if isinstance(cls, dict):
                return cls

        legacy = config.get("classifier")
        if isinstance(legacy, dict):
            return legacy

        return None

    def _resolve_agents_for_run(self, config: dict) -> list[str]:
        requested = config.get("agents")

        if isinstance(requested, list) and requested:
            agents = [str(a).lower() for a in requested if a]
            source = "config.agents"
        else:
            agents = [str(a).lower() for a in (self.agents_to_run or self.default_agents)]
            source = "self.agents_to_run/default"

        # classifier is a prestep; never allow as a node
        agents = [a for a in agents if a != "classifier"]

        # De-dupe while preserving order
        deduped: List[str] = []
        seen = set()
        for a in agents:
            if a not in seen:
                seen.add(a)
                deduped.append(a)

        self.logger.info(
            "[orchestrator] resolved agents for run",
            extra={
                "agents_source": source,
                "resolved_agents": deduped,
                "raw_config_agents": requested,
            },
        )
        return deduped


    # ---------------------------------------------------------------------
    # Pattern resolution (NEW)
    # ---------------------------------------------------------------------

    def _resolve_pattern_for_run(self, config: Dict[str, Any]) -> str:
        """
        Pattern selection priority:
        1) config["execution_config"]["graph_pattern"]
        2) config["graph_pattern"] (legacy/simple)
        3) self.graph_pattern (instance default)
        """
        exec_cfg = config.get("execution_config") or {}
        if isinstance(exec_cfg, dict):
            p = exec_cfg.get("graph_pattern")
            if isinstance(p, str) and p.strip():
                return p.strip()

        p2 = config.get("graph_pattern")
        if isinstance(p2, str) and p2.strip():
            return p2.strip()

        return (self.graph_pattern or self.DEFAULT_PATTERN).strip()


    # ---------------------------------------------------------------------
    # Graph building
    # ---------------------------------------------------------------------

    async def _get_compiled_graph(
            self,
            *,
            pattern_name: str,
            execution_state: Optional[Dict[str, Any]] = None,
            chosen_target: Optional[str] = None,
    ) -> Any:
        graph_agents = [a for a in (self.agents_to_run or []) if str(a).lower() != "classifier"]
        key = (pattern_name.strip(), tuple(graph_agents), bool(self.enable_checkpoints))

        if self._compiled_graph is None or self._compiled_graph_key != key:
            self._compiled_graph = None
            self._compiled_graph_key = key

            self.logger.info(
                "Building LangGraph StateGraph using GraphFactory...",
                extra={"pattern": pattern_name, "agents": graph_agents},
            )

            # --- existing build logic continues ---
            cfg = GraphConfig(
                agents_to_run=graph_agents,
                enable_checkpoints=self.enable_checkpoints,
                memory_manager=self.memory_manager,
                pattern_name=pattern_name.strip(),
                cache_enabled=True,
                execution_state=execution_state or {},
                chosen_target=chosen_target,
            )

            cfg = self.graph_factory.prepare_config(cfg)
            graph_agents = cfg.agents_to_run

            if not self.graph_factory.validate_agents(graph_agents):
                raise GraphBuildError(f"Invalid agents: {graph_agents}")

            self._compiled_graph = self.graph_factory.create_graph(cfg)

            self.logger.info(
                "Successfully built LangGraph StateGraph",
                extra={"agents": graph_agents, "pattern": pattern_name.strip(), "checkpoints": self.enable_checkpoints},
            )

        return self._compiled_graph


    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    async def run(self, query: str, config: Optional[Dict[str, Any]] = None) -> AgentContext:
        config = config or {}
        start_time = time.time()

        # correlation context
        provided_correlation_id = config.get("correlation_id")
        provided_workflow_id = config.get("workflow_id")

        if provided_correlation_id:
            workflow_id = provided_workflow_id or str(uuid.uuid4())
            context_correlation_id.set(provided_correlation_id)
            context_workflow_id.set(workflow_id)
            context_trace_metadata.set({})
            correlation_ctx = CorrelationContext(
                correlation_id=provided_correlation_id,
                workflow_id=workflow_id,
                metadata={},
            )
        else:
            correlation_ctx = ensure_correlation_context()

        execution_id = correlation_ctx.workflow_id
        correlation_id = correlation_ctx.correlation_id

        orchestrator_span = create_child_span("langgraph_orchestrator")
        add_trace_metadata("orchestrator_type", "langgraph-real")
        add_trace_metadata("query_length", len(query))

        # resolve pattern for THIS run
        pattern_name = self._resolve_pattern_for_run(config)
        add_trace_metadata("graph_pattern", pattern_name)

        # resolve agents (requested/default)
        resolved_agents = self._resolve_agents_for_run(config)

        # If agent set changed => rebuild
        if resolved_agents != [a.lower() for a in (self.agents_to_run or [])]:
            self._compiled_graph = None
            self._graph = None

        self.agents_to_run = resolved_agents

        raw_cfg_agents = config.get("agents")
        caller_forced_agents = isinstance(raw_cfg_agents, list) and bool(raw_cfg_agents)

        try:
            thread_id = self.memory_manager.get_thread_id(config.get("thread_id"))
            initial_state = create_initial_state(query, execution_id, correlation_id)

            # Ensure state has execution_state BEFORE compiling
            initial_state = initial_state or {}
            exec_state = initial_state.get("execution_state")
            if not isinstance(exec_state, dict):
                exec_state = {}
                initial_state["execution_state"] = exec_state

            # NEW: expose the same dict under 'exec_state' so downstream nodes
            # (like _ensure_rag_for_final / FinalAgent) can read it consistently.
            initial_state["exec_state"] = exec_state

            # Persist the *original* user question once, for all downstream agents.
            exec_state.setdefault("original_query", query)

            # Deterministic execution_config for all agents
            exec_state["execution_config"] = _canonical_execution_config(config)

            # Optional debugging info
            if "raw_request_config" not in exec_state and isinstance(config, dict):
                exec_state["raw_request_config"] = dict(config)

            # Ensure routing has happened (or compute chosen_target here)
            chosen_target = exec_state.get("route")
            if not isinstance(chosen_target, str) or not chosen_target:
                router = DBQueryRouter(data_query_target="data_query", default_target="refiner")
                chosen_target = router(AgentContext(query=initial_state.get("query", "") or query))
                exec_state["route"] = chosen_target

            decision_selected: Optional[List[str]] = None
            if not caller_forced_agents:
                try:
                    decision_ctx = NodeExecutionContext(
                        workflow_id=execution_id,
                        correlation_id=correlation_id,
                        query=query,
                        execution_state=initial_state.get("execution_state", {}),
                        cognitive_classification=(initial_state.get("classifier") or None),
                    )
                    decision = await self.decision_node.execute(decision_ctx)

                    decision_selected = list(decision.get("selected_agents") or [])
                except Exception as e:
                    self.logger.warning(
                        f"[orchestrator] DecisionNode failed, using existing agents: {e}"
                    )
                    decision_selected = None

            # ✅ If DBQueryRouter decided this is an action/data_query route,
            # use the canonical agent plan for that route_key.
            if not caller_forced_agents:
                route_key = exec_state.get("route_key")
                if route_key:
                    try:
                        route_agents = planned_agents_for_route_key(route_key)
                        if route_agents:
                            self.logger.info(
                                "[orchestrator] Overriding DecisionNode agents from route_key",
                                extra={
                                    "route_key": route_key,
                                    "route_agents": route_agents,
                                    "decision_selected": decision_selected,
                                },
                            )
                            decision_selected = route_agents
                    except Exception as e:
                        self.logger.warning(
                            f"[orchestrator] Failed to apply route_key-based planning: {e}",
                            extra={"route_key": route_key},
                        )




            final_candidates = decision_selected if decision_selected is not None else self.agents_to_run
            final_agents = normalize_agents(final_candidates)

            if final_agents != self.agents_to_run:
                self._compiled_graph = None
                self._graph = None

            self.agents_to_run = final_agents

            _ensure_effective_queries(initial_state, query)

            # Optional RAG prefetch (mutates exec_state in-place, including rag_snippet)
            await self._prefetch_rag(query=query, state=initial_state)

            if not validate_state_integrity(initial_state):
                raise NodeExecutionError("Initial state validation failed")

            if self.memory_manager.is_enabled():
                self.memory_manager.create_checkpoint(
                    thread_id=thread_id,
                    state=initial_state,
                    agent_step="initialization",
                    metadata={"execution_id": execution_id, "query": query},
                )

            # Build and run the graph
            compiled_graph = await self._get_compiled_graph(
                pattern_name=pattern_name,
                execution_state=exec_state,
                chosen_target=chosen_target,
            )

            self.logger.info(
                "Executing LangGraph StateGraph",
                extra={"thread_id": thread_id, "pattern": pattern_name, "agents": self.agents_to_run},
            )

            context = OSSSContext(
                thread_id=thread_id,
                execution_id=execution_id,
                query=query,
                correlation_id=ensure_correlation_context().correlation_id,
                enable_checkpoints=self.enable_checkpoints,
            )

            final_state = await compiled_graph.ainvoke(initial_state, context=context)

            if not validate_state_integrity(final_state):
                self.logger.warning("Final state validation failed, but proceeding")

            if self.memory_manager.is_enabled():
                self.memory_manager.create_checkpoint(
                    thread_id=thread_id,
                    state=final_state,
                    agent_step="completion",
                    metadata={
                        "execution_id": execution_id,
                        "query": query,
                        "successful_agents": final_state["successful_agents"],
                        "failed_agents": final_state["failed_agents"],
                        "completion_status": "success",
                        "pattern": pattern_name,
                    },
                )

            agent_context = await self._convert_state_to_context(final_state)

            total_time_ms = (time.time() - start_time) * 1000
            agent_context.execution_state.update(
                {
                    "orchestrator_type": "langgraph-real",
                    "execution_id": execution_id,
                    "correlation_id": correlation_id,
                    "orchestrator_span": orchestrator_span,
                    "thread_id": thread_id,
                    "agents_requested": self.agents_to_run,
                    "graph_pattern": pattern_name,
                    "config": config,
                    "execution_time_ms": total_time_ms,
                    "langgraph_execution": True,
                    "checkpoints_enabled": self.memory_manager.is_enabled(),
                    "successful_agents_count": len(final_state["successful_agents"]),
                    "failed_agents_count": len(final_state["failed_agents"]),
                    "errors_count": len(final_state["errors"]),
                    "correlation_context": correlation_ctx.to_dict(),
                }
            )

            # emit workflow completed
            def truncate_output(output: Any) -> str:
                if isinstance(output, str):
                    return output[:200] + "..." if len(output) > 200 else output
                content = str(output)
                return content[:200] + "..." if len(content) > 200 else content

            await emit_workflow_completed(
                workflow_id=execution_id,
                status="completed" if not final_state["failed_agents"] else "partial_failure",
                execution_time_seconds=total_time_ms / 1000,
                agent_outputs={k: truncate_output(v) for k, v in agent_context.agent_outputs.items()},
                successful_agents=list(final_state["successful_agents"]),
                failed_agents=list(final_state["failed_agents"]),
                correlation_id=correlation_id,
                metadata={
                    "orchestrator_type": "langgraph-real",
                    "orchestrator_span": orchestrator_span,
                    "thread_id": thread_id,
                    "pattern": pattern_name,
                    "total_agents": len(self.agents_to_run),
                },
            )

            if final_state["failed_agents"]:
                self.failed_executions += 1
            else:
                self.successful_executions += 1

            return agent_context

        except Exception as e:
            self.failed_executions += 1
            total_time_ms = (time.time() - start_time) * 1000

            await emit_workflow_completed(
                workflow_id=execution_id,
                status="failed",
                execution_time_seconds=total_time_ms / 1000,
                error_message=str(e),
                successful_agents=[],
                failed_agents=list(self.agents_to_run or []),
                error_type=e.__class__.__name__,
                error_details={
                    "exception_module": e.__class__.__module__,
                    "exception_qualname": getattr(e.__class__, "__qualname__", e.__class__.__name__),
                },
                correlation_id=correlation_id,
                metadata={
                    "orchestrator_type": "langgraph-real",
                    "orchestrator_span": orchestrator_span,
                    "error_type": type(e).__name__,
                },
            )

            error_context = AgentContext(query=query)
            error_context.execution_state.update(
                {
                    "orchestrator_type": "langgraph-real",
                    "execution_id": execution_id,
                    "correlation_id": correlation_id,
                    "orchestrator_span": orchestrator_span,
                    "agents_requested": self.agents_to_run,
                    "execution_time_ms": total_time_ms,
                    "langgraph_execution": True,
                    "execution_error": str(e),
                    "execution_error_type": type(e).__name__,
                    "correlation_context": correlation_ctx.to_dict(),
                }
            )
            error_context.add_agent_output(
                "langgraph_error",
                f"LangGraph execution failed: {e}\n"
                f"Execution ID: {execution_id}\n"
                f"Requested agents: {', '.join(self.agents_to_run)}",
            )
            raise NodeExecutionError(f"LangGraph execution failed: {e}") from e
        finally:
            # Any cleanup or additional logging can be placed here if necessary
            pass

    # ---------------------------------------------------------------------
    # State -> context conversion
    # ---------------------------------------------------------------------

    async def _convert_state_to_context(self, final_state: OSSSState) -> AgentContext:
        context = AgentContext(query=final_state["query"])

        context.execution_state["structured_outputs"] = final_state.get("structured_outputs", {}) or {}

        try:
            exec_state = final_state.get("execution_state", {}) or {}
            if isinstance(exec_state, dict):
                # ✅ Option A: preserve deterministic config snapshot
                ex_cfg = exec_state.get("execution_config")
                if isinstance(ex_cfg, dict):
                    context.execution_state["execution_config"] = ex_cfg

                # ✅ preserve original_query if present
                oq = exec_state.get("original_query")
                if isinstance(oq, str) and oq.strip():
                    context.execution_state["original_query"] = oq

                # existing behavior
                eff = exec_state.get("effective_queries")
                if isinstance(eff, dict):
                    context.execution_state["effective_queries"] = eff

                # ✅ propagate RAG context into AgentContext
                rag_context = exec_state.get("rag_context")
                if rag_context:
                    context.execution_state["rag_context"] = rag_context
                    context.execution_state["rag_hits"] = exec_state.get("rag_hits", [])
                    context.execution_state["rag_meta"] = exec_state.get("rag_meta", {})
        except Exception:
            # don't let diagnostics break the response
            pass

        if final_state.get("refiner"):
            refiner_final: Optional[RefinerState] = final_state["refiner"]
            if refiner_final is not None:
                context.add_agent_output("refiner", refiner_final["refined_question"])
                context.execution_state["refiner_topics"] = refiner_final["topics"]
                context.execution_state["refiner_confidence"] = refiner_final["confidence"]

        if final_state.get("critic"):
            critic_output: Optional[CriticState] = final_state["critic"]
            if critic_output is not None:
                context.add_agent_output("critic", critic_output["critique"])
                context.execution_state["critic_suggestions"] = critic_output["suggestions"]
                context.execution_state["critic_severity"] = critic_output["severity"]

        if final_state.get("historian"):
            historian_output: Optional[HistorianState] = final_state["historian"]
            if historian_output is not None:
                context.add_agent_output("historian", historian_output["historical_summary"])
                context.execution_state["historian_retrieved_notes"] = historian_output["retrieved_notes"]
                context.execution_state["historian_search_strategy"] = historian_output["search_strategy"]
                context.execution_state["historian_topics_found"] = historian_output["topics_found"]
                context.execution_state["historian_confidence"] = historian_output["confidence"]

        # final_state is presumably the LangGraph state dict at the end of the run
        if final_state.get("final"):
            final_output: Optional[FinalState] = final_state["final"]
            if final_output is not None:
                # Main user-facing answer
                context.add_agent_output("final", final_output["final_answer"])

                # Optional: store structured final info in execution_state for downstream consumers
                context.execution_state["final_used_rag"] = final_output["used_rag"]
                context.execution_state["final_rag_excerpt"] = final_output.get("rag_excerpt")
                context.execution_state["final_sources_used"] = final_output["sources_used"]
                context.execution_state["final_timestamp"] = final_output["timestamp"]

        for agent in final_state["successful_agents"]:
            context.successful_agents.add(agent)

        if final_state["errors"]:
            context.execution_state["langgraph_errors"] = final_state["errors"]

        return context

    # ---------------------------------------------------------------------
    # Pattern controls (NEW)
    # ---------------------------------------------------------------------

    def set_graph_pattern(self, pattern_name: str) -> None:
        if pattern_name not in self.graph_factory.get_available_patterns():
            raise ValueError(
                f"Unknown pattern: {pattern_name}. Available: {self.graph_factory.get_available_patterns()}"
            )
        self.graph_pattern = pattern_name
        self._compiled_graph = None
        self._graph = None
        self.logger.info(f"Graph pattern set to: {pattern_name}")

    def get_available_graph_patterns(self) -> List[str]:
        return self.graph_factory.get_available_patterns()

    # ---------------------------------------------------------------------
    # Stats / diagnostics
    # ---------------------------------------------------------------------

    def get_execution_statistics(self) -> Dict[str, Any]:
        success_rate = (self.successful_executions / self.total_executions) if self.total_executions else 0.0
        return {
            "orchestrator_type": "langgraph-real",
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": success_rate,
            "agents_to_run": self.agents_to_run,
            "graph_factory_stats": self.graph_factory.get_cache_stats(),
            "available_patterns": self.graph_factory.get_available_patterns(),
            "default_pattern": self.graph_pattern,
        }

    def get_dag_structure(self) -> Dict[str, Any]:
        dependencies = get_node_dependencies()
        return {
            "nodes": self.agents_to_run,
            "dependencies": dependencies,
            "entry_point": "refiner",
        }

    # ---------------------------------------------------------------------
    # Routing decision (existing)
    # ---------------------------------------------------------------------

    async def _make_routing_decision(
        self, query: str, available_agents: List[str], config: Dict[str, Any]
    ) -> "RoutingDecision":
        if not self.resource_optimizer:
            raise ValueError("Resource optimizer not available for routing decision")

        # NOTE: keep your existing logic here; this is a safe/minimal default.
        constraints = ResourceConstraints(
            max_execution_time_ms=config.get("max_execution_time_ms"),
            max_agents=config.get("max_agents", 4),
            min_agents=config.get("min_agents", 1),
            min_success_rate=config.get("min_success_rate", 0.7),
        )

        # very light “context requirements” (adjust as needed)
        context_requirements = {
            "requires_final": True,
            "requires_refinement": True,
        }

        # simplistic complexity placeholder
        complexity_score = min(max(len(query) / 500.0, 0.1), 1.0)

        # simplistic performance data placeholder
        performance_data = {a: {"success_rate": 0.8, "average_time_ms": 2000.0, "performance_score": 0.7}
                            for a in available_agents}

        return self.resource_optimizer.select_optimal_agents(
            available_agents=available_agents,
            complexity_score=complexity_score,
            performance_data=performance_data,
            constraints=constraints,
            strategy=self.optimization_strategy,
            context_requirements=context_requirements,
        )
