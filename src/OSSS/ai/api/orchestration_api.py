"""
LangGraph Orchestration API implementation.

Production implementation of OrchestrationAPI that wraps the existing
LangGraphOrchestrator to provide a stable external interface.

Design goals of this module:
- Provide a *stable* API surface (OrchestrationAPI) to external callers
  even if the internal orchestration engine changes over time.
- Centralize lifecycle operations (initialize/shutdown).
- Track active workflows for status endpoints and basic observability.
- Emit workflow lifecycle events (started/completed) for telemetry.
- Persist workflow metadata/results to the database without making DB failures
  break the user-facing API response.
- Support optional markdown export and optional persistence of that export.
"""

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------

import uuid                 # Unique workflow IDs (UUID4)
import asyncio              # Async primitives (sleep, cancellation patterns)
import time                 # Wall-clock timing for execution durations
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone  # UTC timestamps for telemetry/metadata
from pathlib import Path     # Filesystem paths (markdown export)
import json
import re
import os
from copy import deepcopy

from OSSS.ai.config.openai_config import OpenAIConfig
from OSSS.ai.llm.openai import OpenAIChatLLM

# ---------------------------------------------------------------------------
# OSSS / OSSS API contracts and models
# ---------------------------------------------------------------------------

from OSSS.ai.api.external import OrchestrationAPI
from OSSS.ai.api.models import (
    WorkflowRequest,        # Input request model for workflow execution
    WorkflowResponse,       # Output response model for workflow execution
    StatusResponse,         # Response model for status polling
)
from OSSS.ai.api.base import APIHealthStatus          # API-level health response model
from OSSS.ai.diagnostics.health import HealthStatus   # Health enum: HEALTHY/DEGRADED/UNHEALTHY

# Decorator that ensures initialize() has been called before API methods run
from OSSS.ai.api.decorators import ensure_initialized

# The production orchestrator that actually runs the LangGraph pipeline
from OSSS.ai.orchestration.orchestrator import LangGraphOrchestrator

# Observability helpers (structured logger)
from OSSS.ai.observability import get_logger

# Workflow lifecycle events (for metrics/traces/audit logs)
from OSSS.ai.events import emit_workflow_started, emit_workflow_completed

# Database / persistence infrastructure
from OSSS.ai.database.connection import get_session_factory
from OSSS.ai.database.repositories.question_repository import QuestionRepository
from OSSS.ai.database.session_factory import DatabaseSessionFactory
from OSSS.ai.llm.utils import call_llm_text


# Module-level logger (structured)
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Intent → agents mapping (Fix #1: branch-exclusive action)
# ---------------------------------------------------------------------------

ACTION_AGENTS = ["refiner", "data_query", "final"]
READ_AGENTS   = ["refiner", "final"]   # optional alternative
ANALYSIS_AGENTS = ["refiner", "historian", "final"]


def select_agents(intent: str) -> list[str]:
    intent = (intent or "").strip().lower()
    if intent == "action":
        return ACTION_AGENTS
    return ANALYSIS_AGENTS


def _norm_agents(seq: Any) -> list[str]:
    """Normalize agent names to lowercase strings, drop empties."""
    if not isinstance(seq, list):
        return []
    out: list[str] = []
    for a in seq:
        if a is None:
            continue
        s = str(a).strip().lower()
        if s:
            out.append(s)
    return out


def _dedupe(seq: list[str]) -> list[str]:
    out: list[str] = []
    seen = set()
    for a in seq:
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out


def _strip_classifier(seq: list[str]) -> list[str]:
    return [a for a in seq if a != "classifier"]


def _is_empty_agents(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, list):
        return len(_norm_agents(value)) == 0
    return True


def _executed_agents_from_context(ctx: Any) -> list[str]:
    """
    Option A: derive executed agents from context's execution status bookkeeping.

    We prefer 'completed' agents (i.e., actually ran) over 'planned' agents.

    Expected shapes supported (best-effort):
      - ctx.agent_execution_status: {agent_name: {"completed_at": ..., ...}, ...}
      - ctx.execution_status: same shape
      - ctx.execution_state["agent_execution_status"]: same shape
      - fallback: ctx.agent_outputs keys (less reliable)
    """
    # 1) Direct attributes
    for attr in ("agent_execution_status", "execution_status"):
        status = getattr(ctx, attr, None)
        if isinstance(status, dict):
            executed: list[str] = []
            seen = set()
            for name, st in status.items():
                if not name:
                    continue
                if isinstance(st, dict) and st.get("completed_at") is not None:
                    n = str(name).strip().lower()
                    if n and n not in seen:
                        executed.append(n)
                        seen.add(n)
            if executed:
                return executed

    # 2) From execution_state if present
    exec_state = getattr(ctx, "execution_state", None)
    if isinstance(exec_state, dict):
        status = exec_state.get("agent_execution_status")
        if isinstance(status, dict):
            executed: list[str] = []
            seen = set()
            for name, st in status.items():
                if isinstance(st, dict) and st.get("completed_at") is not None:
                    n = str(name).strip().lower()
                    if n and n not in seen:
                        executed.append(n)
                        seen.add(n)
            if executed:
                return executed

    # 3) Fallback: agent_outputs keys
    ao = getattr(ctx, "agent_outputs", None)
    if isinstance(ao, dict) and ao:
        return [str(k).strip().lower() for k in ao.keys() if k]

    return []


def _db_persist_enabled() -> bool:
    return os.getenv("OSSS_AI_DB_PERSIST_ENABLED", "true").lower() in ("1", "true", "yes", "on")


class LangGraphOrchestrationAPI(OrchestrationAPI):
    """
    Production orchestration API wrapping LangGraphOrchestrator.

    This class is the "public" façade:
    - It owns the orchestrator instance and its lifecycle.
    - It exposes stable API methods (execute_workflow, status, cancel, metrics).
    - It adapts internal AgentContext results into API response models.
    - It integrates observability: health checks, metrics, event emission.
    - It integrates persistence: store workflow results and optional markdown.
    """

    def __init__(self) -> None:
        # -------------------------------------------------------------------
        # Internal orchestration engine
        # -------------------------------------------------------------------
        # Created lazily during initialize(). Keep None until then to avoid
        # importing/constructing complex dependencies during module import.
        self._orchestrator: Optional[LangGraphOrchestrator] = None

        # Tracks whether initialize() has been run.
        # The ensure_initialized decorator uses this as part of its checks.
        self._initialized = False

        # -------------------------------------------------------------------
        # In-memory workflow tracking
        # -------------------------------------------------------------------
        # This is used for:
        # - status polling (/status)
        # - simple metrics (active workflow counts)
        # - debugging in development
        #
        # NOTE: This is process-local memory; it will not survive restarts.
        self._active_workflows: Dict[str, Dict[str, Any]] = {}

        # A simple counter of how many workflows this API instance has processed.
        self._total_workflows = 0

        # -------------------------------------------------------------------
        # Database session factories
        # -------------------------------------------------------------------
        # Primary session factory used for persisting Question records.
        self._session_factory = None  # type: ignore[assignment]

        # Optional "repository factory" session manager used for historian
        # document persistence (markdown export).
        self._db_session_factory: Optional[DatabaseSessionFactory] = None

        # -------------------------------------------------------------------
        # Query profile idempotency (prevents double LLM calls)
        # -------------------------------------------------------------------
        self._query_profile_cache: Dict[str, Dict[str, Any]] = {}   # workflow_id -> query_profile dict
        self._query_profile_locks: Dict[str, asyncio.Lock] = {}     # workflow_id -> lock


    def clear_graph_cache(self) -> dict[str, Any]:
        """
        Clear the compiled graph cache via the underlying LangGraphOrchestrator.

        This is intended to be called by admin / maintenance routes.
        It returns a small structured payload that the /admin/cache/clear
        route (or the factory helper) can send back to clients.
        """
        if not self._initialized or self._orchestrator is None:
            logger.warning(
                "[orchestration_api] clear_graph_cache called but API/orchestrator "
                "is not initialized",
                extra={
                    "event": "graph_cache_clear_not_initialized",
                    "api_initialized": self._initialized,
                    "has_orchestrator": self._orchestrator is not None,
                },
            )
            return {
                "status": "error",
                "reason": "not_initialized",
                "api_initialized": self._initialized,
                "has_orchestrator": self._orchestrator is not None,
            }

        # Grab stats before/after if available
        stats_before = None
        stats_after = None

        if hasattr(self._orchestrator, "get_graph_cache_stats"):
            try:
                stats_before = self._orchestrator.get_graph_cache_stats()
            except Exception as e:
                logger.warning(
                    "[orchestration_api] Failed to fetch graph cache stats before clear",
                    extra={"error": str(e)},
                    exc_info=True,
                )

        if not hasattr(self._orchestrator, "clear_graph_cache"):
            logger.warning(
                "[orchestration_api] clear_graph_cache requested but orchestrator "
                "does not implement clear_graph_cache()",
                extra={"event": "graph_cache_clear_unsupported"},
            )
            return {
                "status": "error",
                "reason": "orchestrator_clear_not_supported",
                "stats_before": stats_before,
            }

        logger.info(
            "[orchestration_api] Clearing graph cache via orchestrator",
            extra={"event": "graph_cache_clear_request"},
        )

        try:
            result = self._orchestrator.clear_graph_cache()
        except Exception as e:
            logger.exception(
                "[orchestration_api] Error while clearing graph cache",
                extra={"event": "graph_cache_clear_error", "error": str(e)},
            )
            return {
                "status": "error",
                "reason": "exception",
                "error": str(e),
                "stats_before": stats_before,
            }

        if hasattr(self._orchestrator, "get_graph_cache_stats"):
            try:
                stats_after = self._orchestrator.get_graph_cache_stats()
            except Exception as e:
                logger.warning(
                    "[orchestration_api] Failed to fetch graph cache stats after clear",
                    extra={"error": str(e)},
                    exc_info=True,
                )

        # Normalize result to a dict
        if isinstance(result, dict):
            payload = result
        else:
            payload = {"detail": str(result)}

        return {
            "status": "ok",
            "source": "orchestrator",
            "stats_before": stats_before,
            "stats_after": stats_after,
            **payload,
        }

    def _get_session_factory(self):
        if not _db_persist_enabled():
            # Keep this quiet; callers may check often
            logger.debug("DB persistence disabled; session factory unavailable")
            return None
        if self._session_factory is None:
            self._session_factory = get_session_factory()
        return self._session_factory

    def _normalize_classifier_profile(self, out: Any) -> Dict[str, Any]:
        """
        Normalize classifier output into a dict shape we can safely persist in config.

        Supports either:
          - dict-like outputs
          - objects with attributes (intent, confidence, domain, topics, labels, raw, etc.)

        NEW:
          Includes `domain`, `domain_confidence`, `topic`,
          `topic_confidence`, and `topics` if present.
        """
        if out is None:
            out = {}

        def _get(key: str, default: Any = None) -> Any:
            if isinstance(out, dict):
                return out.get(key, default)
            return getattr(out, key, default)

        # ---- Intent & confidence
        intent = _get("intent")
        confidence = _get("confidence", 0.0)
        try:
            confidence_f = float(confidence or 0.0)
        except Exception:
            confidence_f = 0.0

        # ---- Domain & topic enrichment (new)
        domain = _get("domain")
        domain_conf = _get("domain_confidence")
        try:
            domain_conf_f = float(domain_conf or 0.0) if domain_conf is not None else None
        except Exception:
            domain_conf_f = None

        topic = _get("topic")
        topic_conf = _get("topic_confidence")
        try:
            topic_conf_f = float(topic_conf or 0.0) if topic_conf is not None else None
        except Exception:
            topic_conf_f = None

        topics = _get("topics")
        if topics is not None and not isinstance(topics, list):
            try:
                topics = list(topics)
            except Exception:
                topics = [str(topics)]

        # ---- Assemble normalized profile
        return {
            "intent": intent,
            "confidence": confidence_f,

            # NEW fields
            "domain": domain,
            "domain_confidence": domain_conf_f,
            "topic": topic,
            "topic_confidence": topic_conf_f,
            "topics": topics,

            # legacy or passthrough fields
            "labels": _get("labels"),
            "raw": _get("raw"),
        }

    def _convert_agent_outputs_to_serializable(
        self,
        agent_outputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Convert agent outputs into JSON-serializable structures.

        Why this exists:
        - Historically agent outputs were strings.
        - Newer agents may return Pydantic models (structured outputs).
        - API responses must be serializable (dict/str/list/primitive),
          so we normalize any Pydantic objects via model_dump().

        Parameters
        ----------
        agent_outputs : Dict[str, Any]
            Raw agent outputs which may contain:
            - Pydantic models
            - plain strings
            - dicts/lists/primitive values

        Returns
        -------
        Dict[str, Any]
            Outputs with any Pydantic models converted to dicts.
        """
        serialized_outputs: Dict[str, Any] = {}

        for agent_name, output in agent_outputs.items():
            # Pydantic model detection: model_dump exists on Pydantic v2 models
            if hasattr(output, "model_dump"):
                serialized_outputs[agent_name] = output.model_dump()
            else:
                # Leave already-serializable outputs unchanged
                serialized_outputs[agent_name] = output

        return serialized_outputs

    # -----------------------------------------------------------------------
    # API identity metadata
    # -----------------------------------------------------------------------

    @property
    def api_name(self) -> str:
        """Human-friendly name for diagnostics / health endpoints."""
        return "LangGraph Orchestration API"

    @property
    def api_version(self) -> str:
        """Version string for API clients and telemetry correlation."""
        return "1.0.0"

    # -----------------------------------------------------------------------
    # Lifecycle management
    # -----------------------------------------------------------------------

    async def initialize(self) -> None:
        """
        Initialize the API and its underlying resources.

        Responsibilities:
        - Instantiate the orchestrator (LangGraphOrchestrator)
        - Mark API as initialized so ensure_initialized allows execution
        """
        if self._initialized:
            # Idempotent initialization: safe to call multiple times
            return

        logger.info("Initializing LangGraphOrchestrationAPI")

        # Create orchestrator instance (production pipeline runner)
        self._orchestrator = LangGraphOrchestrator()

        # Mark initialization complete
        self._initialized = True

        logger.info("LangGraphOrchestrationAPI initialized successfully")

    async def shutdown(self) -> None:
        """
        Clean shutdown of orchestrator and resources.

        Responsibilities:
        - Attempt to cancel active workflows (best-effort)
        - Cleanup orchestrator caches if supported
        - Reset initialized flag

        NOTE:
        The underlying orchestrator currently does not expose a formal shutdown(),
        so cleanup is limited to what we can do safely (e.g., cache clearing).
        """
        if not self._initialized:
            return

        logger.info("Shutting down LangGraphOrchestrationAPI")

        # Cancel any active workflows (best-effort)
        for workflow_id in list(self._active_workflows.keys()):
            await self.cancel_workflow(workflow_id)

        # Orchestrator cleanup hook (if implemented)
        if self._orchestrator:
            if hasattr(self._orchestrator, "clear_graph_cache"):
                self._orchestrator.clear_graph_cache()

        self._initialized = False
        logger.info("LangGraphOrchestrationAPI shutdown complete")

    # -----------------------------------------------------------------------
    # Health and metrics endpoints
    # -----------------------------------------------------------------------

    async def health_check(self) -> APIHealthStatus:
        """
        Comprehensive health check including orchestrator status.

        Health strategy:
        - If API isn't initialized -> UNHEALTHY
        - If orchestrator missing -> UNHEALTHY
        - If orchestrator stats indicate high failure rate -> DEGRADED
        - Otherwise -> HEALTHY

        Returns:
            APIHealthStatus with:
            - overall status
            - human-readable details
            - structured "checks" map for dashboards
        """
        checks = {
            "initialized": self._initialized,
            "orchestrator_available": self._orchestrator is not None,
            "active_workflows": len(self._active_workflows),
            "total_workflows_processed": self._total_workflows,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        status = HealthStatus.HEALTHY
        details = (
            f"LangGraph Orchestration API - {len(self._active_workflows)} active workflows"
        )

        # If orchestrator exists and API is initialized, we can perform deeper checks
        if self._orchestrator and self._initialized:
            try:
                # Orchestrator statistics provide a health signal (failures vs total)
                if hasattr(self._orchestrator, "get_execution_statistics"):
                    orchestrator_stats = self._orchestrator.get_execution_statistics()
                    checks["orchestrator_stats"] = orchestrator_stats

                    total_executions = orchestrator_stats.get("total_executions", 0)
                    failed_executions = orchestrator_stats.get("failed_executions", 0)

                    # Only compute failure rate when we have nonzero executions
                    if total_executions > 0:
                        failure_rate = failed_executions / total_executions
                        checks["failure_rate"] = failure_rate

                        # Arbitrary threshold: degrade health if more than 50% failing
                        if failure_rate > 0.5:
                            status = HealthStatus.DEGRADED
                            details += f" (High failure rate: {failure_rate:.1%})"

            except Exception as e:
                # Any exception in deeper checks degrades health but doesn't crash endpoint
                checks["orchestrator_error"] = str(e)
                status = HealthStatus.DEGRADED
                details += f" (Orchestrator check failed: {e})"

        else:
            # If not initialized or orchestrator missing, API is unhealthy
            if not self._initialized:
                status = HealthStatus.UNHEALTHY
                details = "API not initialized"
            else:
                status = HealthStatus.UNHEALTHY
                details = "Orchestrator not available"

        return APIHealthStatus(status=status, details=details, checks=checks)

    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get API performance and usage metrics.

        This endpoint provides:
        - API-level counters (active workflows, total processed)
        - Orchestrator statistics (if available)
        - Graph cache statistics (if available)
        """
        base_metrics = {
            "active_workflows": len(self._active_workflows),
            "total_workflows_processed": self._total_workflows,
            "api_initialized": self._initialized,
            "api_version": self.api_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # If orchestrator is present and initialized, enrich metrics
        if self._orchestrator and self._initialized:
            try:
                if hasattr(self._orchestrator, "get_execution_statistics"):
                    orchestrator_stats = self._orchestrator.get_execution_statistics()
                    base_metrics.update(
                        {f"orchestrator_{k}": v for k, v in orchestrator_stats.items()}
                    )

                if hasattr(self._orchestrator, "get_graph_cache_stats"):
                    cache_stats = self._orchestrator.get_graph_cache_stats()
                    base_metrics.update(
                        {f"cache_{k}": v for k, v in cache_stats.items()}
                    )

            except Exception as e:
                # Metrics failures should never break API
                base_metrics["metrics_error"] = str(e)

        return base_metrics

    # -----------------------------------------------------------------------
    # Workflow execution
    # -----------------------------------------------------------------------

    async def _execute_direct_llm(self, request: WorkflowRequest) -> WorkflowResponse:
        """
        (Kept for potential future use; Option A enforces classifier and will not
        use this path when no agents are provided.)
        """
        start = time.time()

        workflow_id = str(uuid.uuid4())
        correlation_id = request.correlation_id or f"req-{uuid.uuid4()}"

        llm_config = OpenAIConfig.load()
        llm = OpenAIChatLLM(
            api_key=llm_config.api_key,
            model=llm_config.model,
            base_url=llm_config.base_url,
        )

        system_prompt = (
            request.execution_config.get("system_prompt")
            if isinstance(request.execution_config, dict)
            else None
        ) or "You are a helpful assistant."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.query},
        ]

        llm_text = await llm.chat(messages)

        exec_time = time.time() - start
        return WorkflowResponse(
            workflow_id=workflow_id,
            status="completed",
            correlation_id=correlation_id,
            execution_time_seconds=exec_time,
            agent_output_meta={"_routing": {"source": "direct_llm", "planned_agents": [], "executed_agents": []}},
            agent_outputs={"llm": llm_text},
            error_message=None,
            markdown_export=None,
        )

    @ensure_initialized
    async def execute_workflow(self, request: WorkflowRequest) -> WorkflowResponse:
        """
        Execute a workflow using the production orchestrator.

        NOTE:
        This method is intentionally a thin async wrapper around the real async
        implementation (_execute_workflow_async). This prevents accidental future
        refactors that turn execute_workflow into a sync method (which would break
        FastAPI routes that correctly `await` it).
        """
        return await self._execute_workflow_async(request)

    async def _run_classifier_first(self, query: str, config: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from OSSS.ai.agents.classifier_agent import (
                SklearnIntentClassifierAgent,
            )

            model_path = config.get("classifier_model_path") or "models/domain_topic_intent_classifier.joblib"
            model_version = config.get("classifier_model_version") or "v1"

            agent = SklearnIntentClassifierAgent(
                model_path=model_path,
                model_version=model_version,
            )

            out = await agent.run(query, config)

            # -------------------------------------------------------------
            # ✅ Persist classifier output into config as PRE-STEP metadata
            # -------------------------------------------------------------
            config.setdefault("prestep", {})

            profile_dict = self._normalize_classifier_profile(out)

            config["prestep"]["classifier"] = profile_dict

            # Mark routing source so orchestrator can reliably infer prestep happened
            config["routing_source"] = "caller_with_classifier_prestep"

            logger.info(
                "[api] classifier output",
                extra={
                    "workflow_id": config.get("workflow_id"),
                    "correlation_id": config.get("correlation_id"),
                    "classifier": profile_dict,
                },
            )
            return out

        except Exception as e:
            logger.error(
                "[api] classifier failed; continuing",
                extra={
                    "workflow_id": config.get("workflow_id"),
                    "correlation_id": config.get("correlation_id"),
                    "error": str(e),
                },
                exc_info=True,
            )
            return {"intent": "general", "confidence": 0.0, "model_version": "unknown"}

    async def _execute_workflow_async(self, request: WorkflowRequest) -> WorkflowResponse:
        """
        Actual async implementation for workflow execution.

        OPTION A APPLIED (fixed):
        - If caller provides no agents and no graph_pattern, default to graph_pattern=refiner_final
        - Planned agents become ["refiner"] (NOT ["refiner","output"])
        - Never writes "output" into request.agents (avoids Pydantic validation error)
        - Ensures planned_agents reflects what will actually run
        """
        workflow_id = str(uuid.uuid4())
        start_time = time.time()

        # ----------------------------------------------------------------
        # ✅ Ensure request.agents is never None (event schemas expect a list)
        # ----------------------------------------------------------------
        request.agents = _norm_agents(request.agents)

        # Keep a stable snapshot of the caller-provided execution_config
        original_execution_config = request.execution_config or {}
        if not isinstance(original_execution_config, dict):
            original_execution_config = {}

        # ----------------------------------------------------------------
        # ✅ OPTION A (FASTPATH DEFAULT):
        # If caller did not specify agents AND did not specify a graph pattern,
        # default to informational fastpath: refiner -> output (pattern),
        # but planned/graph agents are just ["refiner"].
        # ----------------------------------------------------------------
        exec_cfg_agents = original_execution_config.get("agents")
        exec_cfg_pattern = original_execution_config.get("graph_pattern")

        # NOTE: request.agents can be None or [] depending on your route normalization.
        caller_agents_norm = _norm_agents(list(request.agents)) if request.agents is not None else []
        caller_forced = bool(caller_agents_norm)

        exec_cfg_agents_norm = _norm_agents(exec_cfg_agents)
        exec_cfg_forced = bool(exec_cfg_agents_norm)

        # ❌ DO NOT auto-set graph_pattern any more.
        # We only treat fastpath as enabled when the caller explicitly asks for it.
        fastpath_default = False

        # If caller explicitly set graph_pattern=refiner_final, treat as fastpath
        fastpath_explicit = (exec_cfg_pattern == "refiner_final")

        if not caller_forced and not exec_cfg_forced and not exec_cfg_pattern:
            logger.info(
                "[api] routing: no agents/pattern from caller; letting classifier/router decide",
                extra={"graph_pattern": None, "planned_agents": None},
            )

        # Recompute after potential update
        original_execution_config = request.execution_config or {}
        if not isinstance(original_execution_config, dict):
            original_execution_config = {}

        exec_cfg_pattern = original_execution_config.get("graph_pattern")
        fastpath = (exec_cfg_pattern == "refiner_final") or fastpath_explicit

        # Build config dict we pass into orchestrator
        config: Dict[str, Any] = dict(original_execution_config)
        routing_enabled = bool(config.get("routing_enabled", True))

        config["workflow_id"] = workflow_id
        if request.correlation_id:
            config["correlation_id"] = request.correlation_id

        # ----------------------------------------------------------------
        # Classifier ALWAYS runs as prestep (not a graph node)
        # ----------------------------------------------------------------
        classifier_out = await self._run_classifier_first(request.query, config)

        try:
            logger.info(f"Starting workflow {workflow_id} with query: {request.query[:100]}...")

            # ----------------------------------------------------------------
            # ✅ Emit workflow_started with a guaranteed non-null list
            # Prefer caller agents, then exec_cfg agents, then safe fallback.
            # ----------------------------------------------------------------
            agents_for_event: List[str] = (
                _norm_agents(request.agents)
                or _norm_agents(original_execution_config.get("agents"))
                or ["refiner"]
            )

            await emit_workflow_started(
                workflow_id=workflow_id,
                query=request.query,
                agents=agents_for_event,
                execution_config=request.execution_config,
                correlation_id=request.correlation_id,
                metadata={"api_version": self.api_version, "start_time": start_time},
            )

            self._active_workflows[workflow_id] = {
                "status": "running",
                "request": request,
                "start_time": start_time,
                "workflow_id": workflow_id,
            }
            self._total_workflows += 1

            # -------------------------------------------------------------
            # Rebuild config after classifier, and re-inject prestep metadata
            # -------------------------------------------------------------
            config = dict(original_execution_config)
            config["workflow_id"] = workflow_id
            if request.correlation_id:
                config["correlation_id"] = request.correlation_id

            classifier_profile = self._normalize_classifier_profile(classifier_out)
            intent = (classifier_profile.get("intent") or "").strip().lower()

            config.setdefault("prestep", {})
            config["prestep"]["classifier"] = classifier_profile
            config.setdefault("routing_source", "caller_with_classifier_prestep")

            # ----------------------------------------------------------------
            # ✅ Planned agents resolution
            #
            # Precedence (non-fastpath):
            # 1) request.agents (non-empty)
            # 2) execution_config["agents"] (non-empty)
            # 3) router/classifier mapping (if routing_enabled)
            # 4) default fallback
            #
            # Fastpath:
            # - planned agents always ["refiner"]
            # ----------------------------------------------------------------
            if fastpath:
                final_agents = ["refiner", "final"]
                routing_source = "fastpath"
            else:
                caller_agents_norm = _norm_agents(list(request.agents)) if request.agents is not None else []
                caller_forced = bool(caller_agents_norm)

                exec_cfg_agents_norm = _norm_agents(config.get("agents"))
                exec_cfg_forced = bool(exec_cfg_agents_norm)

                if caller_forced:
                    final_agents = caller_agents_norm
                    routing_source = "caller"
                elif exec_cfg_forced:
                    final_agents = exec_cfg_agents_norm
                    routing_source = "execution_config"
                elif routing_enabled:
                    final_agents = select_agents(intent)
                    routing_source = "router"
                else:
                    final_agents = ANALYSIS_AGENTS
                    routing_source = "default"

            # Never allow classifier as a graph node; also de-dupe
            final_agents = _dedupe(_strip_classifier(_norm_agents(final_agents)))

            # Guardrail: action intent should include data_query
            if not fastpath and intent == "action" and "data_query" not in final_agents:
                logger.warning(
                    "Action intent but data_query not scheduled; overriding to ACTION_AGENTS",
                    extra={"intent": intent, "planned_agents": final_agents, "routing_source": routing_source},
                )
                final_agents = ACTION_AGENTS
                routing_source = "router_override"

            if not final_agents:
                final_agents = ["refiner", "historian", "final"]
                routing_source = "fallback"

            # What the orchestrator actually executes
            config["agents"] = final_agents
            config["routing_source"] = routing_source

            # Persist classifier as PRE-STEP (NOT a graph node)
            config.setdefault("prestep", {})["classifier"] = classifier_profile
            config["classifier"] = classifier_profile  # legacy convenience

            # ---- routing metadata (what you log/emit / return) ----
            routing_meta = config.setdefault("agent_output_meta", {})
            routing_block = routing_meta.setdefault("_routing", {})
            routing_block["source"] = routing_source
            routing_block["planned_agents"] = final_agents
            routing_block["pre_agents"] = []  # classifier ran as prestep
            routing_meta["_classifier"] = classifier_profile

            logger.info(
                "Execution config received",
                extra={
                    "workflow_id": workflow_id,
                    "raw_execution_config": original_execution_config,
                    "routing_source": routing_source,
                    "agents": final_agents,
                    "graph_pattern": config.get("graph_pattern"),
                },
            )

            if self._orchestrator is None:
                raise RuntimeError("Orchestrator not initialized")

            # ----------------------------------------------------------------
            # Run orchestrator
            # ----------------------------------------------------------------
            if bool(config.get("use_advanced_orchestrator", False)):
                from OSSS.ai.orchestration.advanced_adapter import AdvancedOrchestratorAdapter
                result_context = await AdvancedOrchestratorAdapter().run(request.query, config)
            else:
                logger.info(
                    "[api] final agents being executed",
                    extra={
                        "workflow_id": workflow_id,
                        "correlation_id": request.correlation_id,
                        "agents": config.get("agents"),
                        "routing_source": config.get("routing_source"),
                        "graph_pattern": config.get("graph_pattern"),
                    },
                )
                result_context = await self._orchestrator.run(request.query, config)

                # ----------------------------------------------------------------
                # ✅ OPTION A: persist request execution_config onto ctx.execution_state
                # so downstream agents (especially FinalAgent) can deterministically read
                # request-level flags like use_rag/top_k/etc.
                # ----------------------------------------------------------------
                try:
                    state = getattr(result_context, "execution_state", None)
                    if not isinstance(state, dict):
                        state = {}
                        setattr(result_context, "execution_state", state)

                    # Store the *effective* request config (after your fastpath edits)
                    # This is the canonical location FinalAgent should read.
                    state["execution_config"] = dict(original_execution_config or {})

                    # (Optional but helpful) Store resolved planned agents + pattern too
                    state.setdefault("graph_pattern", config.get("graph_pattern"))
                    state.setdefault("planned_agents", list(config.get("agents") or []))
                except Exception:
                    # Never let metadata persistence break the workflow
                    pass

            execution_time = time.time() - start_time

            # ----------------------------------------------------------------
            # Normalize execution_state access (may not exist on some contexts)
            # ----------------------------------------------------------------
            exec_state: Dict[str, Any] = {}
            try:
                maybe_state = getattr(result_context, "execution_state", None)
                if isinstance(maybe_state, dict):
                    exec_state = maybe_state
            except Exception:
                exec_state = {}

            # ----------------------------------------------------------------
            # Output extraction: structured outputs are preferred
            # ----------------------------------------------------------------
            structured_outputs: Dict[str, Any] = {}
            try:
                so = exec_state.get("structured_outputs", {})
                if isinstance(so, dict):
                    structured_outputs = so
            except Exception:
                structured_outputs = {}

            # ----------------------------------------------------------------
            # ✅ Option A executed_agents = derive from completed bookkeeping
            # ----------------------------------------------------------------
            executed_agents: List[str] = _executed_agents_from_context(result_context)

            # Union in structured_outputs keys if bookkeeping missed any
            if structured_outputs:
                for k in structured_outputs.keys():
                    k2 = str(k).strip().lower()
                    if k2 and k2 not in executed_agents:
                        executed_agents.append(k2)

            raw_agent_outputs: Dict[str, Any] = {}
            try:
                raw_agent_outputs = getattr(result_context, "agent_outputs", {}) or {}
                if not isinstance(raw_agent_outputs, dict):
                    raw_agent_outputs = {}
            except Exception:
                raw_agent_outputs = {}

            agent_outputs_to_serialize: Dict[str, Any] = {}
            for agent_name in executed_agents:
                if agent_name in structured_outputs:
                    agent_outputs_to_serialize[agent_name] = structured_outputs[agent_name]
                else:
                    agent_outputs_to_serialize[agent_name] = raw_agent_outputs.get(agent_name, "")

            serialized_agent_outputs = self._convert_agent_outputs_to_serializable(agent_outputs_to_serialize)

            # ----------------------------------------------------------------
            # ✅ Preserve original refiner output + freeze a response snapshot
            # ----------------------------------------------------------------
            refiner_output_for_response = serialized_agent_outputs.get("refiner")

            # If FinalAgent stashed the full refiner text, use it as a fallback
            if not refiner_output_for_response:
                refiner_output_for_response = exec_state.get("refiner_full_text", "")

            # This is the copy we will return in the HTTP response.
            # It will NOT be mutated by topic analysis / markdown export.
            response_agent_outputs: Dict[str, Any] = dict(serialized_agent_outputs)
            if refiner_output_for_response:
                response_agent_outputs["refiner"] = refiner_output_for_response

            # ----------------------------------------------------------------
            # ✅ Single final answer string for UI clients (prefer output on fastpath)
            # ----------------------------------------------------------------
            candidate = (
                response_agent_outputs.get("output")
                or response_agent_outputs.get("final")
                or response_agent_outputs.get("data_query")
                or response_agent_outputs.get("refiner")
                or ""
            )

            if isinstance(candidate, str):
                final_answer = candidate
            else:
                # structured output -> stable string for UI
                try:
                    final_answer = json.dumps(candidate, ensure_ascii=False, indent=2)
                except Exception:
                    final_answer = str(candidate)

            # Ensure agent_output_meta exists before we enrich it
            agent_output_meta: Dict[str, Any] = {}
            try:
                aom = exec_state.get("agent_output_meta", {})
                if isinstance(aom, dict):
                    agent_output_meta = aom
            except Exception:
                agent_output_meta = {}

            agent_output_meta.setdefault("_result", {})["final_answer_agent"] = (
                "output" if "output" in serialized_agent_outputs else
                "final" if "final" in serialized_agent_outputs else
                "data_query" if "data_query" in serialized_agent_outputs else
                "refiner" if "refiner" in serialized_agent_outputs else
                None
            )
            agent_output_meta["_result"]["final_answer"] = final_answer

            # ----------------------------------------------------------------
            # Output meta: ensure routing block is consistent and includes executed_agents
            # ----------------------------------------------------------------
            agent_output_meta["_routing"] = {
                "source": config.get("routing_source", "unknown"),
                "selected_workflow_id": config.get("selected_workflow_id"),
                "planned_agents": config.get("agents"),
                "pre_agents": config.get("pre_agents", []),
                "executed_agents": executed_agents,
            }
            agent_output_meta["_classifier"] = classifier_profile

            for agent_name in serialized_agent_outputs.keys():
                env = agent_output_meta.get(agent_name)
                if not isinstance(env, dict):
                    env = {}
                    agent_output_meta[agent_name] = env
                env.setdefault("agent", agent_name)
                env.setdefault("action", "read")

            response = WorkflowResponse(
                workflow_id=workflow_id,
                status="completed",
                agent_outputs=response_agent_outputs,  # ✅ stable snapshot for API + DB
                execution_time_seconds=execution_time,
                correlation_id=request.correlation_id,
                agent_output_meta=agent_output_meta,
                answer=final_answer,
            )

            # ----------------------------------------------------------------
            # Optional markdown export
            # ----------------------------------------------------------------
            if request.export_md:
                try:
                    from OSSS.ai.store.wiki_adapter import MarkdownExporter
                    from OSSS.ai.store.topic_manager import TopicManager
                    from OSSS.ai.llm.openai import OpenAIChatLLM
                    from OSSS.ai.config.openai_config import OpenAIConfig

                    logger.info(f"Exporting markdown for workflow {workflow_id}")

                    llm_config = OpenAIConfig.load()
                    llm = OpenAIChatLLM(
                        api_key=llm_config.api_key,
                        model=llm_config.model,
                        base_url=llm_config.base_url,
                    )

                    topic_manager = TopicManager(llm=llm)

                    try:
                        # ✅ Use a separate copy for topic analysis so it can't mutate the response outputs
                        topic_analysis = await topic_manager.analyze_and_suggest_topics(
                            query=request.query,
                            agent_outputs=deepcopy(response_agent_outputs),
                        )

                        suggested_topics = [s.topic for s in topic_analysis.suggested_topics]
                        suggested_domain = topic_analysis.suggested_domain
                        logger.info(
                            f"Topic analysis completed: {len(suggested_topics)} topics, domain: {suggested_domain}"
                        )
                    except Exception as topic_error:
                        logger.warning(f"Topic analysis failed: {topic_error}")
                        suggested_topics = []
                        suggested_domain = None

                    exporter = MarkdownExporter()
                    md_path = exporter.export(
                        agent_outputs=response_agent_outputs,  # ✅ stable, refiner preserved
                        question=request.query,
                        topics=suggested_topics,
                        domain=suggested_domain,
                    )

                    md_path_obj = Path(md_path)

                    response.markdown_export = {
                        "file_path": str(md_path_obj.absolute()),
                        "filename": md_path_obj.name,
                        "export_timestamp": datetime.now(timezone.utc).isoformat(),
                        "suggested_topics": (suggested_topics[:5] if suggested_topics else []),
                        "suggested_domain": suggested_domain,
                    }

                    logger.info(f"Markdown export successful: {md_path_obj.name}")

                    try:
                        db_session_factory = await self._get_or_create_db_session_factory()

                        if db_session_factory is None:
                            logger.info(
                                "DB persistence disabled; skipping markdown persistence",
                                extra={"workflow_id": workflow_id, "correlation_id": request.correlation_id},
                            )
                        else:
                            async with db_session_factory.get_repository_factory() as repo_factory:
                                doc_repo = repo_factory.historian_documents

                                with open(md_path_obj, "r", encoding="utf-8") as md_file:
                                    markdown_content = md_file.read()

                                topics_list = suggested_topics[:5] if suggested_topics else []

                                # ✅ Use the stable response snapshot for executed agents
                                agents_executed_for_doc = (
                                    list(response.agent_outputs.keys())
                                    if response.agent_outputs
                                    else []
                                )

                                await doc_repo.get_or_create_document(
                                    title=request.query[:200],
                                    content=markdown_content,
                                    source_path=str(md_path_obj.absolute()),
                                    document_metadata={
                                        "workflow_id": workflow_id,
                                        "correlation_id": request.correlation_id,
                                        "topics": topics_list,
                                        "domain": suggested_domain,
                                        "export_timestamp": datetime.now(timezone.utc).isoformat(),
                                        "agents_executed": agents_executed_for_doc,
                                    },
                                )

                                logger.info(
                                    f"Workflow {workflow_id} markdown persisted to database: {md_path_obj.name}"
                                )

                    except Exception as db_persist_error:
                        logger.warning(
                            "Markdown persistence failed; continuing without DB persistence",
                            extra={
                                "workflow_id": workflow_id,
                                "correlation_id": request.correlation_id,
                                "error": str(db_persist_error),
                            },
                            exc_info=True,
                        )

                except Exception as md_error:
                    error_msg = str(md_error)
                    logger.warning(f"Markdown export failed for workflow {workflow_id}: {error_msg}")
                    response.markdown_export = {
                        "error": "Export failed",
                        "message": error_msg,
                        "export_timestamp": datetime.now(timezone.utc).isoformat(),
                    }

            # ----------------------------------------------------------------
            # Persist workflow results to database (best-effort)
            # ----------------------------------------------------------------
            try:
                await self._persist_workflow_to_database(
                    request,
                    response,
                    result_context,
                    workflow_id,
                    original_execution_config,
                )
            except Exception as persist_error:
                logger.error(f"Failed to persist workflow {workflow_id}: {persist_error}")

            self._active_workflows[workflow_id].update(
                {"status": "completed", "response": response, "end_time": time.time()}
            )

            await emit_workflow_completed(
                workflow_id=workflow_id,
                status="completed",
                execution_time_seconds=execution_time,
                agent_outputs=getattr(result_context, "agent_outputs", None),
                correlation_id=request.correlation_id,
                metadata={
                    "api_version": self.api_version,
                    "end_time": time.time(),
                    "agent_output_meta": agent_output_meta,
                },
            )

            logger.info(f"Workflow {workflow_id} completed successfully in {execution_time:.2f}s")
            return response

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Workflow {workflow_id} failed after {execution_time:.2f}s: {e}")

            error_response = WorkflowResponse(
                workflow_id=workflow_id,
                status="failed",
                agent_outputs={},
                execution_time_seconds=execution_time,
                correlation_id=request.correlation_id,
                error_message=str(e),
            )

            await self._persist_failed_workflow_to_database(
                request, error_response, workflow_id, str(e), original_execution_config
            )

            if workflow_id in self._active_workflows:
                self._active_workflows[workflow_id].update(
                    {"status": "failed", "response": error_response, "error": str(e), "end_time": time.time()}
                )

            await emit_workflow_completed(
                workflow_id=workflow_id,
                status="failed",
                execution_time_seconds=execution_time,
                error_message=str(e),
                error_type=type(e).__name__,
                correlation_id=request.correlation_id,
                metadata={"api_version": self.api_version, "end_time": time.time()},
            )

            return error_response

    # -----------------------------------------------------------------------
    # Status and cancellation endpoints
    # -----------------------------------------------------------------------

    @ensure_initialized
    async def get_status(self, workflow_id: str) -> StatusResponse:
        """
        Get workflow execution status.

        This implementation uses the in-memory _active_workflows store.
        It provides approximate progress for running workflows using
        a simplistic elapsed-time heuristic.

        Raises:
            KeyError if workflow_id is unknown
        """
        if workflow_id not in self._active_workflows:
            raise KeyError(f"Workflow {workflow_id} not found")

        workflow = self._active_workflows[workflow_id]
        status = workflow["status"]

        progress = 0.0
        current_agent = None
        estimated_completion = None

        if status in ("completed", "failed"):
            progress = 100.0
        elif status == "running":
            elapsed = time.time() - workflow["start_time"]
            progress = min(90.0, (elapsed / 10.0) * 100.0)
            current_agent = "synthesis"
            estimated_completion = max(1.0, 10.0 - elapsed)

        return StatusResponse(
            workflow_id=workflow_id,
            status=status,
            progress_percentage=progress,
            current_agent=current_agent,
            estimated_completion_seconds=estimated_completion,
        )

    @ensure_initialized
    async def cancel_workflow(self, workflow_id: str) -> bool:
        """
        Cancel a running workflow.

        IMPORTANT LIMITATION:
        The underlying orchestrator does not currently support mid-flight cancellation.
        This method is therefore "soft-cancel":
        - mark status cancelled
        - remove from in-memory tracking shortly after
        """
        if workflow_id not in self._active_workflows:
            return False

        workflow = self._active_workflows[workflow_id]

        if workflow["status"] in ["completed", "failed"]:
            return False

        workflow["status"] = "cancelled"
        workflow["end_time"] = time.time()

        logger.info(f"Workflow {workflow_id} marked as cancelled")

        await asyncio.sleep(1)

        if workflow_id in self._active_workflows:
            del self._active_workflows[workflow_id]

        return True

    # -----------------------------------------------------------------------
    # Database session factory for markdown persistence
    # -----------------------------------------------------------------------

    async def _get_or_create_db_session_factory(
        self,
    ) -> Optional[DatabaseSessionFactory]:

        if not _db_persist_enabled():
            logger.debug("DB persistence disabled; markdown DB session factory unavailable")
            return None

        if self._db_session_factory is None:
            try:
                self._db_session_factory = DatabaseSessionFactory()
                await self._db_session_factory.initialize()
                logger.info("Database session factory initialized for markdown persistence")
            except Exception as e:
                logger.warning(
                    "Failed to initialize database session factory for markdown persistence",
                    extra={"error": str(e)},
                    exc_info=True,
                )
                self._db_session_factory = None

        return self._db_session_factory

    # -----------------------------------------------------------------------
    # Database persistence helpers (best-effort)
    # -----------------------------------------------------------------------

    async def _persist_workflow_to_database(
        self,
        request: WorkflowRequest,
        response: WorkflowResponse,
        execution_context: Any,
        workflow_id: str,
        original_execution_config: Dict[str, Any],
    ) -> None:
        sf = self._get_session_factory()
        if sf is None:
            logger.debug("DB persistence disabled; skipping workflow persistence")
            return

        # Prefer the planned agents actually executed by the orchestrator (if present)
        planned_agents: List[str] = []

        try:
            aom = getattr(response, "agent_output_meta", None)

            if isinstance(aom, dict):
                routing = aom.get("_routing")

                if isinstance(routing, dict):
                    planned_agents = _norm_agents(routing.get("planned_agents"))
        except Exception:
            planned_agents = []

        if not planned_agents:
            planned_agents = (
                _norm_agents(request.agents)
                or _norm_agents(original_execution_config.get("agents"))
                or ["refiner"]
            )

        execution_metadata = {
            "workflow_id": workflow_id,
            "execution_time_seconds": response.execution_time_seconds,
            "agent_outputs": response.agent_outputs,
            # ✅ Never persist "output" as an agent; persist the planned agent nodes
            "agents_requested": planned_agents,
            "export_md": (request.export_md if request.export_md is not None else False),
            "execution_config": original_execution_config,
            "api_version": self.api_version,
            "orchestrator_type": "langgraph-real",
        }
        nodes_executed = list(response.agent_outputs.keys()) if response.agent_outputs else []

        try:
            async with sf() as session:
                question_repo = QuestionRepository(session)
                await question_repo.create_question(
                    query=request.query,
                    correlation_id=request.correlation_id,
                    execution_id=workflow_id,
                    nodes_executed=nodes_executed,
                    execution_metadata=execution_metadata,
                )
            logger.info("Workflow persisted to database", extra={"workflow_id": workflow_id})
        except Exception as e:
            logger.warning(
                "Workflow persistence failed; continuing without DB persistence",
                extra={"workflow_id": workflow_id, "correlation_id": request.correlation_id, "error": str(e)},
                exc_info=True,
            )

    def _session_factory_or_none(self):
        return self._get_session_factory()

    async def _persist_failed_workflow_to_database(
        self,
        request: WorkflowRequest,
        response: WorkflowResponse,
        workflow_id: str,
        error_message: str,
        original_execution_config: Dict[str, Any],
    ) -> None:
        sf = self._get_session_factory()
        if sf is None:
            logger.debug("DB persistence disabled; skipping failed workflow persistence")
            return

        planned_agents: List[str] = []

        try:
            aom = getattr(response, "agent_output_meta", None)

            if isinstance(aom, dict):
                routing = aom.get("_routing")

                if isinstance(routing, dict):
                    planned_agents = _norm_agents(routing.get("planned_agents"))
        except Exception:
            planned_agents = []

        if not planned_agents:
            planned_agents = _norm_agents(request.agents) or _norm_agents(
                original_execution_config.get("agents")
            ) or ["refiner"]

        execution_metadata = {
            "workflow_id": workflow_id,
            "execution_time_seconds": response.execution_time_seconds,
            "agent_outputs": response.agent_outputs,
            # ✅ Never persist "output" as an agent; persist the planned agent nodes
            "agents_requested": planned_agents,
            "export_md": (request.export_md if request.export_md is not None else False),
            "execution_config": original_execution_config,
            "api_version": self.api_version,
            "orchestrator_type": "langgraph-real",
            "status": "failed",
            "error_message": error_message,
        }
        nodes_executed = list(response.agent_outputs.keys()) if response.agent_outputs else []

        try:
            async with sf() as session:
                question_repo = QuestionRepository(session)
                await question_repo.create_question(
                    query=request.query,
                    correlation_id=request.correlation_id,
                    execution_id=workflow_id,
                    nodes_executed=nodes_executed,
                    execution_metadata=execution_metadata,
                )
            logger.info("Failed workflow persisted to database", extra={"workflow_id": workflow_id})
        except Exception as e:
            logger.warning(
                "Failed workflow persistence failed; continuing without DB persistence",
                extra={"workflow_id": workflow_id, "correlation_id": request.correlation_id, "error": str(e)},
                exc_info=True,
            )

    # -----------------------------------------------------------------------
    # Debugging and monitoring helpers
    # -----------------------------------------------------------------------

    def get_active_workflows(self) -> Dict[str, Dict[str, Any]]:
        return {
            wf_id: {
                "status": wf["status"],
                "start_time": wf["start_time"],
                "query": wf["request"].query[:100],
                "agents": wf["request"].agents,
                "elapsed_seconds": time.time() - wf["start_time"],
            }
            for wf_id, wf in self._active_workflows.items()
        }

    def get_workflow_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        workflows = list(self._active_workflows.values())
        workflows.sort(key=lambda x: x["start_time"], reverse=True)

        return [
            {
                "workflow_id": wf.get("workflow_id", "unknown"),
                "status": wf["status"],
                "query": wf["request"].query[:100],
                "start_time": wf["start_time"],
                "execution_time": wf.get("end_time", time.time()) - wf["start_time"],
            }
            for wf in workflows[:limit]
        ]

    async def get_workflow_history_from_database(
        self,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        try:
            sf = self._get_session_factory()
            if sf is None:
                logger.debug("DB persistence disabled; skipping workflow history fetch")
                return []

            async with sf() as session:
                question_repo = QuestionRepository(session)
                questions = await question_repo.get_recent_questions(limit=limit, offset=offset)

            return [
                {
                    "workflow_id": q.execution_id or str(q.id),
                    "status": "completed",
                    "query": q.query[:100] if q.query else "",
                    "start_time": q.created_at.timestamp(),
                    "execution_time": (
                        q.execution_metadata.get("execution_time_seconds", 0.0)
                        if q.execution_metadata
                        else 0.0
                    ),
                }
                for q in questions
            ]

        except Exception as e:
            logger.error(f"Failed to retrieve workflow history: {e}")
            return []

    def find_workflow_by_correlation_id(self, correlation_id: str) -> Optional[str]:
        for workflow_id, workflow_data in self._active_workflows.items():
            req = workflow_data.get("request")
            if req and getattr(req, "correlation_id", None) == correlation_id:
                return workflow_id
        return None

    @ensure_initialized
    async def get_status_by_correlation_id(self, correlation_id: str) -> StatusResponse:
        workflow_id = self.find_workflow_by_correlation_id(correlation_id)
        if workflow_id is None:
            raise KeyError(f"No workflow found for correlation_id: {correlation_id}")
        return await self.get_status(workflow_id)
