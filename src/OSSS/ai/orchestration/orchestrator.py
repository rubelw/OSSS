# OSSS/ai/orchestration/orchestrator.py
from __future__ import annotations

"""
Production LangGraph orchestrator for OSSS agents.

Contract Superset Mode (Fix 1, best-practice):

- Pattern names are **contracts** and must be canonical only (e.g. "standard", "data_query").
- "superset" is **NOT** a pattern name (never appears in graph-patterns.json, never passed to PatternService).
- Superset behavior is expressed via **compile strategy** only:
    - config["compile_variant"] == "superset" and/or config["agents_superset"] == True
- Planner MUST emit a canonical contract pattern (NOT "superset").
- GraphFactory compiles using the canonical pattern, but may use compile_variant="superset"
  to build a superset-capable graph (cache/compile strategy label, not a pattern).

This orchestrator:
- Runs planner first
- Writes execution_state["execution_plan"] for observability/debugging (pattern is canonical)
- Canonicalizes the plan object handed to GraphFactory so plan.pattern matches execution_plan.pattern
"""

import os
import time
import uuid
from dataclasses import dataclass, is_dataclass, replace
from typing import Any, Dict, List, Optional

from OSSS.ai.agents.base_agent import BaseAgent
from OSSS.ai.agents.registry import get_agent_registry
from OSSS.ai.context import AgentContext
from OSSS.ai.correlation import (
    CorrelationContext,
    add_trace_metadata,
    context_correlation_id,
    context_trace_metadata,
    context_workflow_id,
    create_child_span,
    ensure_correlation_context,
)
from OSSS.ai.events import emit_workflow_completed
from OSSS.ai.observability import get_logger
from OSSS.ai.orchestration.graph_factory import GraphBuildError, GraphFactory
from OSSS.ai.orchestration.memory_manager import OSSSMemoryManager, create_memory_manager
from OSSS.ai.orchestration.node_wrappers import NodeExecutionError, get_node_dependencies
from OSSS.ai.orchestration.routers import build_default_router_registry
from OSSS.ai.orchestration.state_bridge import AgentContextStateBridge
from OSSS.ai.orchestration.state_schemas import (
    CriticState,
    ExecutionConfig,
    ExecutionState,
    FinalState,
    HistorianState,
    OSSSContext,
    OSSSState,
    RefinerState,
    create_initial_state,
    validate_state_integrity,
)

# ✅ Planner + plan type
from OSSS.ai.orchestration.planning.defaults import build_default_planner
from OSSS.ai.orchestration.planning.plan import ExecutionPlan

# Existing (optional) enhanced routing/optimizer
from OSSS.ai.routing import (
    OptimizationStrategy,
    ResourceConstraints,
    ResourceOptimizer,
    RoutingDecision,
)

from OSSS.ai.rag.additional_index_rag import RagResult, rag_prefetch_additional

logger = get_logger(__name__)

DEFAULT_RAG_JSONL_PATH = os.getenv(
    "OSSS_RAG_JSONL_PATH",
    "/workspace/vector_indexes/main/embeddings.jsonl",
)

# -----------------------------------------------------------------------------
# Contract Superset Mode helpers (Fix 1)
# -----------------------------------------------------------------------------

OPTION_MODE = "contract_superset"

_CANONICAL_PATTERNS: tuple[str, ...] = ("standard", "data_query")
_CANONICAL_PATTERN_DEFAULT = "data_query"

_SUPERSET_COMPILE_VARIANT = "superset"

# ✅ Option A: if agents_superset is enabled and caller didn't provide agents,
# force a real superset agent list into config["agents"] so downstream compilers
# that depend on it behave deterministically.
_SUPERSET_AGENTS_DEFAULT: tuple[str, ...] = (
    "refiner",
    "data_query",
    "historian",
    "final",
)


def _require_canonical_pattern(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s == "superset":
        raise ValueError(
            "Contract Superset Mode (Fix 1): 'superset' is NOT a pattern name. "
            "Emit pattern='standard'/'data_query' and set compile_variant='superset' (or agents_superset=True)."
        )
    if s not in _CANONICAL_PATTERNS:
        raise ValueError(f"Invalid pattern name {s!r}. Allowed: {list(_CANONICAL_PATTERNS)}")
    return s


def _ensure_superset_compile_strategy(exec_state: Dict[str, Any], config: Dict[str, Any]) -> None:
    """
    Ensure the per-run config/exec_state expresses superset behavior as a compile strategy (not a pattern).
    """
    config.setdefault("compile_variant", _SUPERSET_COMPILE_VARIANT)
    config.setdefault("agents_superset", True)

    ec = exec_state.get("execution_config")
    if isinstance(ec, dict):
        ec.setdefault("compile_variant", _SUPERSET_COMPILE_VARIANT)
        ec.setdefault("agents_superset", True)


def _canonicalize_agent_list(raw_agents: Any) -> list[str]:
    if not isinstance(raw_agents, (list, tuple)):
        return []
    out: list[str] = []
    seen = set()
    for a in raw_agents:
        s = str(a).strip().lower()
        if not s:
            continue
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _normalize_agents_for_entry_point(raw: Any, *, entry_point: str) -> list[str]:
    """
    ✅ FIX: DO NOT force 'refiner' for wizard/collect_details fast-path.

    Rules:
    - Always ensure 'final' exists (last).
    - If entry_point == 'refiner': ensure 'refiner' exists (first).
    - If entry_point != 'refiner': DO NOT inject 'refiner' (planner may be intentionally skipping it).
    - Preserve other agent names, deduped, and ensure entry_point is present and first.
    """
    ep = str(entry_point or "").strip().lower() or "refiner"
    agents = _canonicalize_agent_list(raw)

    # Ensure entry_point is present and first
    agents = [a for a in agents if a != ep]
    agents.insert(0, ep)

    # If entry point is refiner, ensure refiner stays first (already)
    if ep == "refiner":
        agents = [a for a in agents if a != "refiner"]
        agents.insert(0, "refiner")

    # Always ensure final is last
    agents = [a for a in agents if a != "final"]
    agents.append("final")

    out: list[str] = []
    seen = set()
    for a in agents:
        if a and a not in seen:
            seen.add(a)
            out.append(a)
    return out


def _ensure_config_agents_superset_if_needed(config: Dict[str, Any]) -> bool:
    """
    ✅ Option A implementation.

    If agents_superset is enabled and the caller didn't supply a non-empty config["agents"],
    inject a stable superset agent list into config["agents"].

    Returns True if we injected agents, else False.
    """
    if not isinstance(config, dict):
        return False

    if not bool(config.get("agents_superset")):
        return False

    existing = config.get("agents")
    if isinstance(existing, list) and any(str(x).strip() for x in existing):
        return False

    config["agents"] = list(_SUPERSET_AGENTS_DEFAULT)
    return True


def _canonicalize_plan_for_compile(
    plan: Any,
    *,
    pattern: str,
    agents: list[str],
    entry_point: str,
    route: Optional[str],
    route_locked: bool,
) -> Any:
    """
    Ensure the plan object handed to GraphFactory.compile() matches the authoritative
    execution_state["execution_plan"] (pattern is canonical in Fix 1).

    ✅ FIX: also canonicalize entry_point/route fields so GraphFactory and routers
    start where the planner intended (e.g., wizard collect_details starts at data_query).
    """
    p = plan.normalized() if hasattr(plan, "normalized") else plan

    if is_dataclass(p):
        kwargs: Dict[str, Any] = {}
        if hasattr(p, "pattern"):
            kwargs["pattern"] = pattern
        if hasattr(p, "graph_pattern"):
            kwargs["graph_pattern"] = pattern

        if hasattr(p, "agents"):
            kwargs["agents"] = list(agents)
        if hasattr(p, "agents_to_run"):
            kwargs["agents_to_run"] = list(agents)

        if hasattr(p, "entry_point"):
            kwargs["entry_point"] = entry_point
        if hasattr(p, "chosen_target"):
            kwargs["chosen_target"] = entry_point  # legacy consumers

        if hasattr(p, "route"):
            kwargs["route"] = route
        if hasattr(p, "route_locked"):
            kwargs["route_locked"] = bool(route_locked)

        try:
            return replace(p, **kwargs)
        except Exception:
            pass

    try:
        if hasattr(p, "pattern"):
            setattr(p, "pattern", pattern)
        if hasattr(p, "graph_pattern"):
            setattr(p, "graph_pattern", pattern)

        if hasattr(p, "agents"):
            setattr(p, "agents", list(agents))
        if hasattr(p, "agents_to_run"):
            setattr(p, "agents_to_run", list(agents))

        if hasattr(p, "entry_point"):
            setattr(p, "entry_point", entry_point)
        if hasattr(p, "chosen_target"):
            setattr(p, "chosen_target", entry_point)

        if hasattr(p, "route"):
            setattr(p, "route", route)
        if hasattr(p, "route_locked"):
            setattr(p, "route_locked", bool(route_locked))
    except Exception:
        pass

    return p


def _canonical_execution_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produce a single deterministic ``execution_config`` mapping.

    Supports both shapes:
      A) nested: ``config["execution_config"] = {...}``
      B) flat:   ``config["use_rag"] = ...``, ``config["top_k"] = ...``, etc.
    """
    if not isinstance(config, dict):
        return {}

    base: Dict[str, Any] = {}
    nested = config.get("execution_config")
    if isinstance(nested, dict):
        base.update(nested)

    for k in (
        "parallel_execution",
        "timeout_seconds",
        "use_llm_intent",
        "use_rag",
        "top_k",
        "graph_pattern",
        "compile_variant",
        "agents_superset",
    ):
        if k in config and k not in base:
            base[k] = config[k]

    # RAG normalization
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

    if rag.get("enabled") and not rag.get("jsonl_path"):
        rag["jsonl_path"] = DEFAULT_RAG_JSONL_PATH

    if rag:
        base["rag"] = rag

    # final_llm normalization + env fallback
    final_llm = base.get("final_llm")
    if isinstance(final_llm, dict):
        provider = str(final_llm.get("provider", "")).lower()
        if provider == "gateway" and not final_llm.get("base_url"):
            env_base = os.getenv("OSSS_AI_GATEWAY_BASE_URL")
            if env_base:
                final_llm["base_url"] = env_base
        base["final_llm"] = final_llm

    return base


def _ensure_effective_queries(state: Dict[str, Any], base_query: str) -> None:
    exec_state = state.setdefault("execution_state", {})
    if not isinstance(exec_state, dict):
        state["execution_state"] = {}
        exec_state = state["execution_state"]

    effective = exec_state.setdefault("effective_queries", {})
    if not isinstance(effective, dict):
        exec_state["effective_queries"] = {}
        effective = exec_state["effective_queries"]

    effective.setdefault("user", base_query)


# -----------------------------------------------------------------------------
# RAG settings (unchanged)
# -----------------------------------------------------------------------------

@dataclass
class RagIndexConfig:
    name: str = "main"
    default_top_k: int = 6
    max_snippet_chars: int = 6000


@dataclass
class RagSettings:
    indexes: Dict[str, RagIndexConfig]


RAG_SETTINGS = RagSettings(
    indexes={
        "main": RagIndexConfig(name="main", default_top_k=6, max_snippet_chars=6000),
        "tutor": RagIndexConfig(name="tutor", default_top_k=4, max_snippet_chars=4000),
        "agent": RagIndexConfig(name="agent", default_top_k=3, max_snippet_chars=3000),
    }
)


def _resolve_rag_config(
    raw_index_name: str,
    rag_cfg: Dict[str, Any],
) -> tuple[str, int, int]:
    base_cfg = RAG_SETTINGS.indexes.get(raw_index_name, RagIndexConfig(name=raw_index_name))
    effective_index = str(rag_cfg.get("index", base_cfg.name))
    top_k = int(rag_cfg.get("top_k", base_cfg.default_top_k or 5))
    snippet_max_chars = int(rag_cfg.get("snippet_max_chars", base_cfg.max_snippet_chars or 6000))
    return effective_index, top_k, snippet_max_chars


class LangGraphOrchestrator:
    """
    Production LangGraph orchestrator for OSSS agents.
    """

    # Contract Superset Mode: default runtime contract pattern
    DEFAULT_PATTERN = _CANONICAL_PATTERN_DEFAULT

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
        self.default_agents = ["refiner"]

        self._compiled_graph = None
        # Fix 1: cache key includes compile_variant
        self._compiled_graph_key: Optional[
            tuple[str, str, str, bool, bool]] = None  # (pattern, variant, entry_point, checkpoints, cache)

        self.use_enhanced_routing = use_enhanced_routing
        self.optimization_strategy = optimization_strategy
        self._markdown_export_service = None  # type: ignore[assignment]

        self.resource_optimizer: Optional[ResourceOptimizer] = (
            ResourceOptimizer() if self.use_enhanced_routing else None
        )

        self.agents_to_run = agents_to_run or self.default_agents
        self.enable_checkpoints = enable_checkpoints
        self.thread_id = thread_id
        self.registry = get_agent_registry()
        self.logger = get_logger(f"{__name__}.LangGraphOrchestrator")

        # Fix 1: accept ONLY canonical contract patterns at init (never 'superset')
        if graph_pattern is not None:
            self.graph_pattern = _require_canonical_pattern(graph_pattern)
        else:
            self.graph_pattern = self.DEFAULT_PATTERN

        self.memory_manager = memory_manager or create_memory_manager(
            enable_checkpoints=enable_checkpoints,
            thread_id=thread_id,
        )

        self.agents: List[BaseAgent] = []

        self.total_executions = 0
        self.successful_executions = 0
        self.failed_executions = 0

        self.state_bridge = AgentContextStateBridge()

        router_registry = build_default_router_registry()
        self.graph_factory = GraphFactory(router_registry=router_registry)

        self._graph = None  # legacy placeholder
        self._compiled_graph = None

        self.planner = build_default_planner()

        self.logger.info(
            "Initialized LangGraphOrchestrator (Contract Superset Mode)",
            extra={
                "agents": self.agents_to_run,
                "default_pattern": self.graph_pattern,
                "checkpoints": self.enable_checkpoints,
                "thread_id": self.thread_id,
                "enhanced_routing": self.use_enhanced_routing,
                "optimization_strategy": self.optimization_strategy.value,
                "mode": OPTION_MODE,
            },
        )

    # ------------------------------------------------------------------
    # RAG prefetch (unchanged)
    # ------------------------------------------------------------------

    async def _prefetch_rag(self, *, query: str, state: OSSSState) -> None:
        exec_state: ExecutionState = state.setdefault("execution_state", {})  # type: ignore[assignment]
        if not isinstance(exec_state, dict):
            exec_state = {}  # type: ignore[assignment]
            state["execution_state"] = exec_state  # type: ignore[assignment]

        cfg: Dict[str, Any] = {}
        canonical_exec_cfg = exec_state.get("execution_config")
        if isinstance(canonical_exec_cfg, dict):
            cfg = canonical_exec_cfg
        legacy_cfg = exec_state.get("config")
        if isinstance(legacy_cfg, dict):
            for k, v in legacy_cfg.items():
                cfg.setdefault(k, v)

        rag_cfg = cfg.get("rag") or {}
        if not isinstance(rag_cfg, dict) or not rag_cfg.get("enabled"):
            self.logger.info("[orchestrator] RAG disabled for this request; skipping prefetch")
            exec_state["rag_enabled"] = False
            exec_state.pop("rag_context", None)
            exec_state.pop("rag_snippet", None)
            exec_state.pop("rag_hits", None)
            return

        rag_mode = str(rag_cfg.get("mode") or os.getenv("OSSS_RAG_MODE", "soft_disable")).lower()
        if rag_mode not in {"hard_fail", "soft_disable", "partial"}:
            rag_mode = "soft_disable"

        rag_context_str: str = ""
        rag_hits: list[dict] = []
        snippet_max_chars: int = int(rag_cfg.get("snippet_max_chars", 6000))

        try:
            raw_index_name = str(rag_cfg.get("index", "main"))
            index_name, top_k, snippet_max_chars = _resolve_rag_config(
                raw_index_name=raw_index_name,
                rag_cfg=rag_cfg,
            )

            embed_model = rag_cfg.get("embed_model", "nomic-embed-text")
            jsonl_path = rag_cfg.get("jsonl_path", DEFAULT_RAG_JSONL_PATH)

            rag_result: RagResult = await rag_prefetch_additional(
                query=query,
                index=index_name,
                top_k=top_k,
            )

            rag_context_str = rag_result.combined_text or ""

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

            exec_state["rag_enabled"] = True
            exec_state["rag_context"] = rag_context_str
            exec_state["rag_snippet"] = rag_context_str[:snippet_max_chars] if rag_context_str else ""
            exec_state["rag_hits"] = rag_hits

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

            self.logger.info(
                "[orchestrator] RAG context stored in execution_state",
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
            self.logger.warning(
                f"[orchestrator] RAG prefetch failed (rag_mode={rag_mode}): {e}",
                extra={"rag_mode": rag_mode},
            )

            if rag_mode == "hard_fail":
                exec_state["rag_enabled"] = False
                exec_state["rag_error"] = str(e)
                raise

            if rag_mode == "partial" and (rag_context_str or rag_hits):
                exec_state["rag_enabled"] = True
                exec_state["rag_partial"] = True
                exec_state["rag_error"] = str(e)
                return

            exec_state["rag_enabled"] = False
            exec_state["rag_error"] = str(e)
            exec_state.pop("rag_context", None)
            exec_state.pop("rag_snippet", None)
            exec_state.pop("rag_hits", None)

    # ---------------------------------------------------------------------
    # Agent list resolution (unchanged)
    # ---------------------------------------------------------------------

    def _resolve_agents_for_run(self, config: dict) -> list[str]:
        requested = config.get("agents")

        if isinstance(requested, list) and requested:
            agents = [str(a).lower() for a in requested if a]
            source = "config.agents"
        else:
            agents = [str(a).lower() for a in (self.agents_to_run or self.default_agents)]
            source = "self.agents_to_run/default"

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
    # Graph building (Fix 1)
    # ---------------------------------------------------------------------

    async def _get_compiled_graph_from_plan(
            self,
            *,
            plan: ExecutionPlan,
            execution_state: Optional[Dict[str, Any]] = None,
    ) -> Any:
        exec_state = execution_state or {}

        cache_enabled = True
        if exec_state.get("suppress_history") or exec_state.get("wizard_bailed"):
            cache_enabled = False

        ep = exec_state.get("execution_plan")
        if not isinstance(ep, dict):
            ep = {}

        # Fix 1: canonical contract pattern is authoritative; never "superset"
        pattern = _require_canonical_pattern(
            ep.get("pattern")
            or getattr(plan, "graph_pattern", None)
            or getattr(plan, "pattern", None)
            or exec_state.get("graph_pattern")
            or self.graph_pattern
        )

        entry_point = str(
            ep.get("entry_point")
            or getattr(plan, "entry_point", None)
            or exec_state.get("entry_point")
            or "refiner"
        ).strip().lower() or "refiner"

        # ✅ FIX: do not force 'refiner' when planner chose entry_point='data_query'
        ep_agents_raw = ep.get("agents") or getattr(plan, "agents_to_run", None) or getattr(plan, "agents", None)
        ep_agents = _normalize_agents_for_entry_point(ep_agents_raw, entry_point=entry_point)

        # Fix 1: compile_variant drives superset compilation (NOT pattern)
        exec_cfg = exec_state.get("execution_config")
        exec_cfg_variant = exec_cfg.get("compile_variant") if isinstance(exec_cfg, dict) else None
        compile_variant = str(
            ep.get("compile_variant") or exec_cfg_variant or _SUPERSET_COMPILE_VARIANT
        ).strip() or _SUPERSET_COMPILE_VARIANT

        # ✅ Fix 1: cache key MUST include entry_point (compiled graphs bake it in)
        key = (pattern, compile_variant, entry_point, bool(self.enable_checkpoints), bool(cache_enabled))

        if self._compiled_graph is None or self._compiled_graph_key != key:
            self._compiled_graph = None
            self._compiled_graph_key = key

            self.logger.info(
                "[orchestrator] compiling graph (Contract Superset Mode)",
                extra={
                    "pattern": pattern,
                    "compile_variant": compile_variant,
                    "cache_enabled": cache_enabled,
                    "checkpoints_enabled": bool(self.enable_checkpoints),
                    "ep_agents": ep_agents,
                    "entry_point": entry_point,
                    "mode": OPTION_MODE,
                },
            )

            route = ep.get("route") or getattr(plan, "route", None) or exec_state.get("route")
            route = str(route).strip().lower() if route else None
            route_locked = bool(
                ep.get("route_locked") if "route_locked" in ep else getattr(plan, "route_locked", False))

            plan_for_compile = _canonicalize_plan_for_compile(
                plan,
                pattern=pattern,
                agents=ep_agents,
                entry_point=entry_point,
                route=route,
                route_locked=route_locked,
            )

            self._compiled_graph = self.graph_factory.compile(
                plan=plan_for_compile,  # type: ignore[arg-type]
                enable_checkpoints=bool(self.enable_checkpoints),
                memory_manager=self.memory_manager,
                cache_enabled=bool(cache_enabled),
                execution_state=exec_state,
                compile_variant=compile_variant,
            )

            self.logger.info(
                "[orchestrator] compiled_graph ready",
                extra={
                    "compiled_key": self._compiled_graph_key,
                    "pattern": pattern,
                    "compile_variant": compile_variant,
                    "cache_enabled": cache_enabled,
                    "checkpoints_enabled": bool(self.enable_checkpoints),
                    "entry_point": entry_point,
                    "mode": OPTION_MODE,
                },
            )

        return self._compiled_graph

    # ---------------------------------------------------------------------
    # Public API (planner + compiler)
    # ---------------------------------------------------------------------

    async def run(self, query: str, config: Optional[Dict[str, Any]] = None) -> AgentContext:
        config = config or {}
        config.setdefault("raw_query", query)

        start_time = time.time()
        self.total_executions += 1

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
        add_trace_metadata("mode", OPTION_MODE)

        resolved_agents = self._resolve_agents_for_run(config)
        if resolved_agents != [a.lower() for a in (self.agents_to_run or [])]:
            self._compiled_graph = None
            self._graph = None
        self.agents_to_run = resolved_agents

        raw_cfg_agents = config.get("agents")
        caller_forced_agents = isinstance(raw_cfg_agents, list) and bool(raw_cfg_agents)

        try:
            thread_id = self.memory_manager.get_thread_id(config.get("thread_id"))
            initial_state = create_initial_state(query, execution_id, correlation_id)

            exec_state: ExecutionState = initial_state.get("execution_state")  # type: ignore[assignment]
            if not isinstance(exec_state, dict):
                exec_state = {}  # type: ignore[assignment]
                initial_state["execution_state"] = exec_state  # type: ignore[assignment]
            initial_state["exec_state"] = exec_state  # back-compat alias

            upstream_exec_state = config.get("execution_state")
            if isinstance(upstream_exec_state, dict) and upstream_exec_state:
                self.logger.info(
                    "[orchestrator] Merging upstream execution_state into initial_state",
                    extra={
                        "event": "merge_upstream_execution_state",
                        "upstream_keys": list(upstream_exec_state.keys()),
                        "mode": OPTION_MODE,
                    },
                )
                exec_state.update(upstream_exec_state)

                tc = upstream_exec_state.get("task_classification")
                cc = upstream_exec_state.get("cognitive_classification")
                if tc is not None and initial_state.get("task_classification") is None:
                    initial_state["task_classification"] = tc  # type: ignore[index]
                if cc is not None and initial_state.get("cognitive_classification") is None:
                    initial_state["cognitive_classification"] = cc  # type: ignore[index]

            suppress_history = bool(exec_state.get("suppress_history") or config.get("suppress_history"))

            if exec_state.get("wizard_bailed") and exec_state.get("wizard_bail_reason") == "user_rejected_table":
                suppress_history = True

            if suppress_history:
                exec_state["checkpoints_skipped"] = True
                thread_id = f"{thread_id}::bail::{execution_id}"
                exec_state["thread_id_overridden"] = True
                exec_state["suppress_history"] = True
                config["suppress_history"] = True

            exec_state.setdefault("original_query", query)

            exec_cfg: ExecutionConfig = _canonical_execution_config(config)  # type: ignore[assignment]
            exec_state["execution_config"] = exec_cfg
            exec_state["config"] = exec_cfg
            exec_state.setdefault("option_mode", OPTION_MODE)

            if "raw_request_config" not in exec_state and isinstance(config, dict):
                exec_state["raw_request_config"] = dict(config)

            # Ensure contract superset compile strategy always present
            _ensure_superset_compile_strategy(exec_state, config)

            # ------------------------------------------------------------------
            # Step 1 — Planner (Fix 1: pattern is canonical contract)
            # ------------------------------------------------------------------
            request = {
                "query": query,
                "config": config,
                "execution_id": execution_id,
                "correlation_id": correlation_id,
            }

            plan: ExecutionPlan = self.planner.plan(exec_state=exec_state, request=request)  # type: ignore[assignment]

            graph_pattern = _require_canonical_pattern(
                getattr(plan, "graph_pattern", None)
                or getattr(plan, "pattern", None)
                or config.get("graph_pattern")
                or self.graph_pattern
            )

            # ✅ FIX: respect planner entry_point (wizard fast-path will be "data_query")
            entry_point = str(getattr(plan, "entry_point", None) or "refiner").strip().lower() or "refiner"
            if entry_point not in {"refiner", "data_query", "historian", "final"}:
                entry_point = "refiner"

            # Route is the planner’s chosen route (if any), else entry_point is the safe default
            plan_route = getattr(plan, "route", None)
            route = str(plan_route).strip().lower() if isinstance(plan_route, str) and plan_route.strip() else entry_point

            route_locked = bool(getattr(plan, "route_locked", False))

            planned_agents = getattr(plan, "agents_to_run", None) or getattr(plan, "agents", None) or []

            # ✅ FIX: normalize agents relative to entry_point (do not inject refiner when skipping it)
            if caller_forced_agents:
                # caller explicitly forced a list: keep it, but still enforce entry_point + final ordering
                forced = _normalize_agents_for_entry_point(self.agents_to_run, entry_point=entry_point)
                self.agents_to_run = forced
            else:
                normalized = _normalize_agents_for_entry_point(planned_agents or self.agents_to_run, entry_point=entry_point)
                if normalized != self.agents_to_run:
                    self._compiled_graph = None
                    self._graph = None
                self.agents_to_run = normalized

            compile_variant = str(
                getattr(plan, "compile_variant", None) or config.get("compile_variant") or _SUPERSET_COMPILE_VARIANT
            ).strip() or _SUPERSET_COMPILE_VARIANT

            # Keep config/exec_state aligned for the compiler
            config["graph_pattern"] = graph_pattern
            config["compile_variant"] = compile_variant
            config["agents_superset"] = True
            if isinstance(exec_state.get("execution_config"), dict):
                exec_state["execution_config"]["graph_pattern"] = graph_pattern
                exec_state["execution_config"]["compile_variant"] = compile_variant
                exec_state["execution_config"]["agents_superset"] = True

            # Authoritative (debuggable) plan payload for this run
            exec_state["execution_plan"] = {
                "pattern": graph_pattern,                # canonical contract only
                "agents": list(self.agents_to_run),      # informational
                "entry_point": entry_point,              # ✅ respect plan
                "route": route,                          # ✅ respect plan
                "route_locked": route_locked,            # ✅ respect plan
                "chosen_target": entry_point,            # legacy: where to start
                "decided_by": getattr(plan, "decided_by", None),
                "reason": getattr(plan, "reason", None),
                "signals": getattr(plan, "signals", None) if isinstance(getattr(plan, "signals", None), dict) else {},
                "compile_variant": compile_variant,      # superset compile strategy
                "agents_superset": True,
                "mode": OPTION_MODE,
            }

            # Back-compat / convenience keys
            exec_state["route"] = route
            exec_state["route_locked"] = route_locked or bool(exec_state.get("route_locked"))
            exec_state["graph_pattern"] = graph_pattern
            exec_state["entry_point"] = entry_point
            exec_state["agents_to_run"] = list(self.agents_to_run)
            exec_state["planned_agents"] = list(self.agents_to_run)
            exec_state["plan_decided_by"] = getattr(plan, "decided_by", None)
            exec_state["plan_reason"] = getattr(plan, "reason", None)

            add_trace_metadata("graph_pattern", graph_pattern)
            add_trace_metadata("compile_variant", compile_variant)
            add_trace_metadata("entry_point", entry_point)
            add_trace_metadata("route", route)

            # ------------------------------------------------------------------
            # Step 2 — RAG prefetch + checkpoints
            # ------------------------------------------------------------------
            _ensure_effective_queries(initial_state, query)
            await self._prefetch_rag(query=query, state=initial_state)

            if not validate_state_integrity(initial_state):
                raise NodeExecutionError("Initial state validation failed")

            if self.memory_manager.is_enabled() and not suppress_history:
                self.memory_manager.create_checkpoint(
                    thread_id=thread_id,
                    state=initial_state,
                    agent_step="initialization",
                    metadata={"execution_id": execution_id, "query": query},
                )

            # ------------------------------------------------------------------
            # Step 3 — Single plan log line (pre-compile)
            # ------------------------------------------------------------------
            cache_enabled = not bool(exec_state.get("suppress_history") or exec_state.get("wizard_bailed"))

            self.logger.info(
                "[orchestrator] execution plan (pre-compile)",
                extra={
                    "execution_id": execution_id,
                    "correlation_id": correlation_id,
                    "thread_id": thread_id,
                    "plan_pattern": graph_pattern,
                    "plan_agents": list(self.agents_to_run),
                    "plan_entry_point": entry_point,        # ✅
                    "plan_chosen_target": entry_point,       # ✅
                    "compile_variant": compile_variant,
                    "route": exec_state.get("route"),
                    "route_locked": bool(exec_state.get("route_locked")),
                    "route_reason": exec_state.get("route_reason"),
                    "plan_decided_by": exec_state.get("plan_decided_by"),
                    "plan_reason": exec_state.get("plan_reason"),
                    "signals": exec_state.get("execution_plan", {}).get("signals", {}),
                    "cache_enabled": bool(cache_enabled),
                    "checkpoints_enabled": bool(self.enable_checkpoints),
                    "mode": OPTION_MODE,
                },
            )

            # ------------------------------------------------------------------
            # Step 4 — Compile (GraphFactory.compile, Fix 1)
            # ------------------------------------------------------------------
            compiled_graph = await self._get_compiled_graph_from_plan(
                plan=plan,
                execution_state=exec_state,
            )

            self.logger.info(
                "Executing LangGraph StateGraph",
                extra={
                    "thread_id": thread_id,
                    "pattern": graph_pattern,
                    "compile_variant": compile_variant,
                    "agents": self.agents_to_run,
                    "route": route,
                    "entry_point": entry_point,
                    "mode": OPTION_MODE,
                },
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

            if self.memory_manager.is_enabled() and not suppress_history:
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
                        "pattern": graph_pattern,
                        "compile_variant": compile_variant,
                        "mode": OPTION_MODE,
                    },
                )

            agent_context = await self._convert_state_to_context(final_state)

            base_exec_state = initial_state.get("execution_state", {})
            ctx_exec_state = getattr(agent_context, "execution_state", {})
            if isinstance(ctx_exec_state, dict):
                base_exec_state.update(ctx_exec_state)
                agent_context.execution_state = base_exec_state

            total_time_ms = (time.time() - start_time) * 1000
            agent_context.execution_state.update(
                {
                    "orchestrator_type": "langgraph-real",
                    "execution_id": execution_id,
                    "correlation_id": correlation_id,
                    "orchestrator_span": orchestrator_span,
                    "thread_id": thread_id,
                    "agents_requested": self.agents_to_run,
                    "graph_pattern": graph_pattern,
                    "compile_variant": compile_variant,
                    "agents_superset": True,
                    "route": route,
                    "entry_point": entry_point,
                    "config": config,
                    "execution_time_ms": total_time_ms,
                    "langgraph_execution": True,
                    "checkpoints_enabled": self.memory_manager.is_enabled(),
                    "successful_agents_count": len(final_state["successful_agents"]),
                    "failed_agents_count": len(final_state["failed_agents"]),
                    "errors_count": len(final_state["errors"]),
                    "correlation_context": correlation_ctx.to_dict(),
                    "option_mode": OPTION_MODE,
                }
            )

            def truncate_output(output: Any) -> str:
                if isinstance(output, str):
                    return output[:200] + "..." if len(output) > 200 else output
                content = str(output)
                return content[:200] + "..." if len(content) > 200 else content

            if getattr(agent_context, "agent_outputs", None) is None:
                self.logger.warning(
                    "[orchestrator] agent_context.agent_outputs was None; initializing to empty dict before emit_workflow_completed",
                    extra={"event": "missing_agent_outputs", "execution_id": execution_id, "correlation_id": correlation_id},
                )
                agent_context.agent_outputs = {}

            safe_agent_outputs = {k: truncate_output(v) for k, v in agent_context.agent_outputs.items()}

            await emit_workflow_completed(
                workflow_id=execution_id,
                status="completed" if not final_state["failed_agents"] else "partial_failure",
                execution_time_seconds=total_time_ms / 1000,
                agent_outputs=safe_agent_outputs,
                successful_agents=list(final_state["successful_agents"]),
                failed_agents=list(final_state["failed_agents"]),
                correlation_id=correlation_id,
                metadata={
                    "orchestrator_type": "langgraph-real",
                    "orchestrator_span": orchestrator_span,
                    "thread_id": thread_id,
                    "pattern": graph_pattern,
                    "compile_variant": compile_variant,
                    "total_agents": len(self.agents_to_run),
                    "mode": OPTION_MODE,
                },
            )

            if final_state["failed_agents"]:
                self.failed_executions += 1
            else:
                self.successful_executions += 1

            return agent_context

        except GraphBuildError as e:
            self.failed_executions += 1
            raise NodeExecutionError(f"Graph compilation failed: {e}") from e

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
                    "mode": OPTION_MODE,
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
                    "option_mode": OPTION_MODE,
                }
            )
            error_context.add_agent_output(
                "langgraph_error",
                f"LangGraph execution failed: {e}\nExecution ID: {execution_id}\nRequested agents: {', '.join(self.agents_to_run)}",
            )
            raise NodeExecutionError(f"LangGraph execution failed: {e}") from e

    # ---------------------------------------------------------------------
    # State -> context conversion (unchanged)
    # ---------------------------------------------------------------------

    async def _convert_state_to_context(self, final_state: OSSSState) -> AgentContext:
        context = AgentContext(query=final_state["query"])
        context.execution_state["structured_outputs"] = (final_state.get("structured_outputs", {}) or {})

        try:
            exec_state = final_state.get("execution_state", {}) or {}
            if isinstance(exec_state, dict):
                ex_cfg = exec_state.get("execution_config") or exec_state.get("config")
                if isinstance(ex_cfg, dict):
                    context.execution_state["execution_config"] = ex_cfg

                oq = exec_state.get("original_query")
                if isinstance(oq, str) and oq.strip():
                    context.execution_state["original_query"] = oq

                eff = exec_state.get("effective_queries")
                if isinstance(eff, dict):
                    context.execution_state["effective_queries"] = eff

                rag_context = exec_state.get("rag_context")
                if rag_context:
                    context.execution_state["rag_context"] = rag_context
                    context.execution_state["rag_hits"] = exec_state.get("rag_hits", [])
                    context.execution_state["rag_meta"] = exec_state.get("rag_meta", {})
        except Exception:
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

        if final_state.get("final"):
            final_output: Optional[FinalState] = final_state["final"]
            if final_output is not None:
                context.add_agent_output("final", final_output["final_answer"])
                context.execution_state["final_used_rag"] = final_output["used_rag"]
                context.execution_state["final_rag_excerpt"] = final_output.get("rag_excerpt")
                context.execution_state["final_sources_used"] = final_output["sources_used"]
                context.execution_state["final_timestamp"] = final_output["timestamp"]

        if getattr(context, "successful_agents", None) is None:
            context.successful_agents = []
        for agent in final_state["successful_agents"]:
            if agent not in context.successful_agents:
                context.successful_agents.append(agent)

        if final_state["errors"]:
            context.execution_state["langgraph_errors"] = final_state["errors"]

        return context

    # ---------------------------------------------------------------------
    # Pattern controls (Fix 1)
    # ---------------------------------------------------------------------

    def set_graph_pattern(self, pattern_name: str) -> None:
        pattern = _require_canonical_pattern(pattern_name)
        self.graph_pattern = pattern
        self._compiled_graph = None
        self._graph = None
        self.logger.info("Graph pattern set to: %s", pattern, extra={"mode": OPTION_MODE})

    def get_available_graph_patterns(self) -> List[str]:
        return list(_CANONICAL_PATTERNS)

    # ---------------------------------------------------------------------
    # Stats / diagnostics (unchanged)
    # ---------------------------------------------------------------------

    def get_execution_statistics(self) -> Dict[str, Any]:
        success_rate = (self.successful_executions / self.total_executions) if self.total_executions else 0.0

        graph_factory_stats: Dict[str, Any] = {"enabled": False}
        try:
            cache = getattr(self.graph_factory, "cache", None)
            if cache and hasattr(cache, "get_stats"):
                graph_factory_stats = cache.get_stats()
                graph_factory_stats["enabled"] = True
        except Exception as e:
            graph_factory_stats = {"enabled": True, "error": str(e)}

        return {
            "orchestrator_type": "langgraph-real",
            "mode": OPTION_MODE,
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": success_rate,
            "agents_to_run": self.agents_to_run,
            "graph_factory_stats": graph_factory_stats,
            "available_patterns": self.get_available_graph_patterns(),
            "default_pattern": self.graph_pattern,
            "default_compile_variant": _SUPERSET_COMPILE_VARIANT,
        }

    def get_dag_structure(self) -> Dict[str, Any]:
        dependencies = get_node_dependencies()
        # entry_point varies per plan; this is just a static view
        return {"nodes": self.agents_to_run, "dependencies": dependencies, "entry_point": "refiner"}

    # ---------------------------------------------------------------------
    # Routing decision (existing; unchanged)
    # ---------------------------------------------------------------------

    async def _make_routing_decision(
        self,
        query: str,
        available_agents: List[str],
        config: Dict[str, Any],
    ) -> "RoutingDecision":
        if not self.resource_optimizer:
            raise ValueError("Resource optimizer not available for routing decision")

        constraints = ResourceConstraints(
            max_execution_time_ms=config.get("max_execution_time_ms"),
            max_agents=config.get("max_agents", 4),
            min_agents=config.get("min_agents", 1),
            min_success_rate=config.get("min_success_rate", 0.7),
        )

        context_requirements = {"requires_final": True, "requires_refinement": True}
        complexity_score = min(max(len(query) / 500.0, 0.1), 1.0)

        performance_data = {
            a: {
                "success_rate": 0.8,
                "average_time_ms": 2000.0,
                "performance_score": 0.7,
            }
            for a in available_agents
        }

        return self.resource_optimizer.select_optimal_agents(
            available_agents=available_agents,
            complexity_score=complexity_score,
            performance_data=performance_data,
            constraints=constraints,
            strategy=self.optimization_strategy,
            context_requirements=context_requirements,
        )
