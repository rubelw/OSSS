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
import json
import os
from copy import deepcopy

# ---------------------------------------------------------------------------
# OSSS services / config
# ---------------------------------------------------------------------------

from OSSS.ai.services.classification_service import ClassificationService
from OSSS.ai.services.workflow_persistence_service import WorkflowPersistenceService
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

# Database / persistence infrastructure (used via helpers/services)
from OSSS.ai.database.connection import get_session_factory
from OSSS.ai.database.session_factory import DatabaseSessionFactory

# Module-level logger (structured)
logger = get_logger(__name__)

def _pick_final_answer(
    agent_outputs: Dict[str, Any],
) -> tuple[str, Optional[str]]:
    """
    Decide which agent's output should be used as the top-level answer.

    Priority:
      1) Any data_query* channel (e.g. "data_query", "data_query:consents")
      2) "final"
      3) "output"
      4) "refiner"
      5) First available key

    For dict-shaped outputs (like data_query canonical_output), we prefer:
      content -> markdown -> table_markdown -> str(dict)
    """

    def _extract_text(val: Any) -> str:
        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            text = (
                val.get("content")
                or val.get("markdown")
                or val.get("table_markdown")
                or val.get("table_markdown_compact")
                or val.get("table_markdown_full")
            )
            if isinstance(text, str):
                return text
        try:
            return json.dumps(val, ensure_ascii=False, indent=2)
        except Exception:
            return str(val)

    if not isinstance(agent_outputs, dict) or not agent_outputs:
        return "", None

    # 1) Prefer any data_query* key (includes "data_query:consents", etc.)
    for key, val in agent_outputs.items():
        k = str(key).strip().lower()
        if not k.startswith("data_query"):
            continue
        text = _extract_text(val).strip()
        if text:
            return text, key

    # 2) final
    if "final" in agent_outputs:
        text = _extract_text(agent_outputs["final"]).strip()
        if text:
            return text, "final"

    # 3) output
    if "output" in agent_outputs:
        text = _extract_text(agent_outputs["output"]).strip()
        if text:
            return text, "output"

    # 4) refiner
    if "refiner" in agent_outputs:
        text = _extract_text(agent_outputs["refiner"]).strip()
        if text:
            return text, "refiner"

    # 5) Last resort: first key
    for key, val in agent_outputs.items():
        text = _extract_text(val).strip()
        if text:
            return text, key

    return "", None


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


def _executed_agents_from_context(ctx: Any) -> list[str]:
    """
    Derive executed agents from context's execution status bookkeeping.

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

    def __init__(
        self,
        orchestrator: Optional[LangGraphOrchestrator] = None,
        classification_service: Optional[ClassificationService] = None,
        persistence_service: Optional[WorkflowPersistenceService] = None,
    ) -> None:
        # -------------------------------------------------------------------
        # Internal orchestration engine
        # -------------------------------------------------------------------
        # If an orchestrator is injected (tests/alt engines), respect it.
        self._orchestrator: Optional[LangGraphOrchestrator] = orchestrator

        # Tracks whether initialize() has been run.
        # If an orchestrator is injected, we treat this as already initialized.
        self._initialized = orchestrator is not None

        # -------------------------------------------------------------------
        # In-memory workflow tracking
        # -------------------------------------------------------------------
        self._active_workflows: Dict[str, Dict[str, Any]] = {}
        self._total_workflows = 0

        # -------------------------------------------------------------------
        # Classification service
        # -------------------------------------------------------------------
        self._classification_service = classification_service or ClassificationService()

        # -------------------------------------------------------------------
        # Database session factories
        # -------------------------------------------------------------------
        self._session_factory = None  # type: ignore[assignment]
        self._db_session_factory: Optional[DatabaseSessionFactory] = None

        # -------------------------------------------------------------------
        # Persistence service (delegated DB writes)
        # -------------------------------------------------------------------
        self._persistence_service = persistence_service or WorkflowPersistenceService(
            session_factory_provider=self._get_session_factory,
            api_version=self.api_version,
        )

        # -------------------------------------------------------------------
        # Markdown export service (lazy-initialized)
        # -------------------------------------------------------------------
        self._markdown_export_service = None  # type: ignore[assignment]

    # -----------------------------------------------------------------------
    # Graph cache helpers
    # -----------------------------------------------------------------------

    def clear_graph_cache(self) -> dict[str, Any]:
        """
        Clear the compiled graph cache via the underlying LangGraphOrchestrator.
        Intended for admin / maintenance routes.
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

        payload = result if isinstance(result, dict) else {"detail": str(result)}

        return {
            "status": "ok",
            "source": "orchestrator",
            "stats_before": stats_before,
            "stats_after": stats_after,
            **payload,
        }

    # -----------------------------------------------------------------------
    # DB session factory helpers
    # -----------------------------------------------------------------------

    def _get_session_factory(self):
        """
        Provider used by WorkflowPersistenceService and any other DB helpers.
        """
        if not _db_persist_enabled():
            # Keep this quiet; callers may check often
            logger.debug("DB persistence disabled; session factory unavailable")
            return None
        if self._session_factory is None:
            self._session_factory = get_session_factory()
        return self._session_factory

    # -----------------------------------------------------------------------
    # Agent output serialization
    # -----------------------------------------------------------------------

    def _convert_agent_outputs_to_serializable(
        self,
        agent_outputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Convert agent outputs into JSON-serializable structures.

        - Pydantic v2 models with model_dump()
        - plain strings
        - dicts/lists/primitive values
        """
        serialized_outputs: Dict[str, Any] = {}

        for agent_name, output in agent_outputs.items():
            if hasattr(output, "model_dump"):
                serialized_outputs[agent_name] = output.model_dump()
            else:
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
        """
        if self._initialized:
            return

        logger.info("Initializing LangGraphOrchestrationAPI")

        # Only create a default orchestrator if one was not injected.
        if self._orchestrator is None:
            self._orchestrator = LangGraphOrchestrator()

        self._initialized = True

        logger.info("LangGraphOrchestrationAPI initialized successfully")

    async def shutdown(self) -> None:
        """
        Clean shutdown of orchestrator and resources.
        """
        if not self._initialized:
            return

        logger.info("Shutting down LangGraphOrchestrationAPI")

        # Cancel any active workflows (best-effort)
        for workflow_id in list(self._active_workflows.keys()):
            await self.cancel_workflow(workflow_id)

        if self._orchestrator and hasattr(self._orchestrator, "clear_graph_cache"):
            self._orchestrator.clear_graph_cache()

        self._initialized = False
        logger.info("LangGraphOrchestrationAPI shutdown complete")

    # -----------------------------------------------------------------------
    # Health and metrics endpoints
    # -----------------------------------------------------------------------

    async def health_check(self) -> APIHealthStatus:
        """
        Comprehensive health check including orchestrator status.
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

        if self._orchestrator and self._initialized:
            try:
                if hasattr(self._orchestrator, "get_execution_statistics"):
                    orchestrator_stats = self._orchestrator.get_execution_statistics()
                    checks["orchestrator_stats"] = orchestrator_stats

                    total_executions = orchestrator_stats.get("total_executions", 0)
                    failed_executions = orchestrator_stats.get("failed_executions", 0)

                    if total_executions > 0:
                        failure_rate = failed_executions / total_executions
                        checks["failure_rate"] = failure_rate

                        if failure_rate > 0.5:
                            status = HealthStatus.DEGRADED
                            details += f" (High failure rate: {failure_rate:.1%})"

            except Exception as e:
                checks["orchestrator_error"] = str(e)
                status = HealthStatus.DEGRADED
                details += f" (Orchestrator check failed: {e})"
        else:
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
        """
        base_metrics = {
            "active_workflows": len(self._active_workflows),
            "total_workflows_processed": self._total_workflows,
            "api_initialized": self._initialized,
            "api_version": self.api_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

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
                base_metrics["metrics_error"] = str(e)

        return base_metrics

    # -----------------------------------------------------------------------
    # Workflow execution
    # -----------------------------------------------------------------------

    async def _execute_direct_llm(self, request: WorkflowRequest) -> WorkflowResponse:
        """
        (Kept for potential future use; currently not used by main orchestration path.)
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
            agent_output_meta={
                "_routing": {
                    "source": "direct_llm",
                    "planned_agents": [],
                    "executed_agents": [],
                }
            },
            agent_outputs={"llm": llm_text},
            error_message=None,
            markdown_export=None,
        )

    @ensure_initialized
    async def execute_workflow(self, request: WorkflowRequest) -> WorkflowResponse:
        """
        Execute a workflow using the production orchestrator.

        Intentionally a thin async wrapper around _execute_workflow_async.
        """
        return await self._execute_workflow_async(request)

    async def _execute_workflow_async(self, request: WorkflowRequest) -> WorkflowResponse:
        """
        Actual async implementation for workflow execution.

        - Orchestration API:
          * normalizes request + execution_config
          * runs classifier as a PRE-STEP only (via ClassificationService)
          * emits workflow_started/finished events
          * calls orchestrator.run(query, config)
          * adapts AgentContext -> WorkflowResponse
          * delegates markdown export + DB persistence to services

        - Orchestrator:
          * owns routing, agent selection, and graph_pattern
          * owns `_routing` metadata in state.agent_output_meta
        """
        workflow_id = str(uuid.uuid4())
        start_time = time.time()

        # Normalize request.agents to a list; do NOT override/invent agents here.
        request.agents = _norm_agents(request.agents)

        # Immutable snapshot of the caller-provided execution_config
        original_execution_config = request.execution_config or {}
        if not isinstance(original_execution_config, dict):
            original_execution_config = {}

        # Base config passed into orchestrator; only meta fields added here.
        config: Dict[str, Any] = dict(original_execution_config)
        config["workflow_id"] = workflow_id
        if request.correlation_id:
            config["correlation_id"] = request.correlation_id

        # Seed execution_state so the classifier and orchestrator share it
        # This allows ClassificationService to write task/cognitive classifications
        # into execution_state *before* the graph/DecisionNode runs.
        execution_state: Dict[str, Any] = dict(
            original_execution_config.get("execution_state") or {}
        )
        config["execution_state"] = execution_state

        # ----------------------------------------------------------------
        # Classifier as PRE-STEP (via ClassificationService)
        # ----------------------------------------------------------------
        classifier_profile = await self._classification_service.classify(
            request.query,
            config,
        )

        config.setdefault("prestep", {})
        config["prestep"]["classifier"] = classifier_profile
        config["classifier"] = classifier_profile  # optional legacy convenience
        config.setdefault("routing_source", "caller_with_classifier_prestep")

        try:
            logger.info(
                f"Starting workflow {workflow_id} with query: {request.query[:100]}..."
            )

            # ----------------------------------------------------------------
            # Emit workflow_started with caller-visible agents (if any).
            # ----------------------------------------------------------------
            agents_for_event: List[str] = (
                _norm_agents(request.agents)
                or _norm_agents(original_execution_config.get("agents"))
                or []
            )

            await emit_workflow_started(
                workflow_id=workflow_id,
                query=request.query,
                agents=agents_for_event,
                execution_config=original_execution_config,
                correlation_id=request.correlation_id,
                metadata={"api_version": self.api_version, "start_time": start_time},
            )

            # In-memory tracking for status
            self._active_workflows[workflow_id] = {
                "status": "running",
                "request": request,
                "start_time": start_time,
                "workflow_id": workflow_id,
            }
            self._total_workflows += 1

            # ----------------------------------------------------------------
            # Run orchestrator (it owns routing, agents, and patterns)
            # ----------------------------------------------------------------
            if self._orchestrator is None:
                raise RuntimeError("Orchestrator not initialized")

            use_advanced = bool(config.get("use_advanced_orchestrator", False))
            if use_advanced:
                from OSSS.ai.orchestration.advanced_adapter import AdvancedOrchestratorAdapter

                logger.info(
                    "[api] Delegating to AdvancedOrchestratorAdapter",
                    extra={
                        "workflow_id": workflow_id,
                        "correlation_id": request.correlation_id,
                    },
                )
                result_context = await AdvancedOrchestratorAdapter().run(
                    request.query, config
                )
            else:
                logger.info(
                    "[api] Delegating to LangGraphOrchestrator",
                    extra={
                        "workflow_id": workflow_id,
                        "correlation_id": request.correlation_id,
                        "caller_agents": agents_for_event,
                        "graph_pattern": original_execution_config.get("graph_pattern"),
                    },
                )
                result_context = await self._orchestrator.run(request.query, config)

            execution_time = time.time() - start_time

            # ----------------------------------------------------------------
            # Normalize execution_state & agent_outputs from AgentContext
            # ----------------------------------------------------------------
            exec_state: Dict[str, Any] = {}
            try:
                maybe_state = getattr(result_context, "execution_state", None)
                if isinstance(maybe_state, dict):
                    exec_state = maybe_state
            except Exception:
                exec_state = {}

            # Structured outputs (preferred) from state
            structured_outputs: Dict[str, Any] = {}
            try:
                so = exec_state.get("structured_outputs", {})
                if isinstance(so, dict):
                    structured_outputs = so
            except Exception:
                structured_outputs = {}

            # Raw agent_outputs from context
            raw_agent_outputs: Dict[str, Any] = {}
            try:
                raw_agent_outputs = getattr(result_context, "agent_outputs", {}) or {}
                if not isinstance(raw_agent_outputs, dict):
                    raw_agent_outputs = {}
            except Exception:
                raw_agent_outputs = {}

            # Determine which agents actually executed
            executed_agents: List[str] = _executed_agents_from_context(result_context)

            # Ensure any structured output agents are included in executed list
            if structured_outputs:
                for k in structured_outputs.keys():
                    k2 = str(k).strip().lower()
                    if k2 and k2 not in executed_agents:
                        executed_agents.append(k2)

            # Merge structured outputs with raw outputs (structured wins)
            agent_outputs_to_serialize: Dict[str, Any] = {}
            for agent_name in executed_agents:
                if agent_name in structured_outputs:
                    agent_outputs_to_serialize[agent_name] = structured_outputs[agent_name]
                else:
                    agent_outputs_to_serialize[agent_name] = raw_agent_outputs.get(agent_name, "")

            serialized_agent_outputs = self._convert_agent_outputs_to_serializable(
                agent_outputs_to_serialize
            )

            # Preserve a stable snapshot for HTTP response
            response_agent_outputs: Dict[str, Any] = dict(serialized_agent_outputs)

            # Preserve refiner output (if available) for clients / exports
            refiner_output_for_response = response_agent_outputs.get("refiner")
            if not refiner_output_for_response:
                refiner_output_for_response = exec_state.get("refiner_full_text", "")
                if refiner_output_for_response:
                    response_agent_outputs["refiner"] = refiner_output_for_response

            # ----------------------------------------------------------------
            # Single final answer string for UI clients
            # ----------------------------------------------------------------
            final_answer, final_answer_agent = _pick_final_answer(response_agent_outputs)

            # ----------------------------------------------------------------
            # agent_output_meta: prefer orchestrator-provided meta, then enrich
            # ----------------------------------------------------------------
            agent_output_meta: Dict[str, Any] = {}
            try:
                aom = exec_state.get("agent_output_meta", {})
                if isinstance(aom, dict):
                    agent_output_meta = deepcopy(aom)
            except Exception:
                agent_output_meta = {}

            routing_block = agent_output_meta.setdefault("_routing", {})
            routing_block.setdefault("source", config.get("routing_source", "unknown"))
            routing_block.setdefault("planned_agents", exec_state.get("planned_agents"))
            routing_block.setdefault("executed_agents", executed_agents)
            routing_block.setdefault("selected_workflow_id", config.get("selected_workflow_id"))
            routing_block.setdefault("pre_agents", [])

            result_meta = agent_output_meta.setdefault("_result", {})
            result_meta["final_answer"] = final_answer
            result_meta["final_answer_agent"] = final_answer_agent

            agent_output_meta["_classifier"] = classifier_profile

            # Ensure each agent has a small env block
            for agent_name in response_agent_outputs.keys():
                env = agent_output_meta.get(agent_name)
                if not isinstance(env, dict):
                    env = {}
                    agent_output_meta[agent_name] = env
                env.setdefault("agent", agent_name)
                env.setdefault("action", "read")

            response = WorkflowResponse(
                workflow_id=workflow_id,
                status="completed",
                agent_outputs=response_agent_outputs,
                execution_time_seconds=execution_time,
                correlation_id=request.correlation_id,
                agent_output_meta=agent_output_meta,
                answer=final_answer,
            )

            # ----------------------------------------------------------------
            # Optional markdown export (delegated to MarkdownExportService)
            # ----------------------------------------------------------------
            if request.export_md:
                try:
                    if getattr(self, "_markdown_export_service", None) is None:
                        from OSSS.ai.services.markdown_export_service import (
                            MarkdownExportService,
                        )

                        self._markdown_export_service = MarkdownExportService(
                            db_session_factory_provider=self._get_or_create_db_session_factory
                        )

                    md_info = await self._markdown_export_service.export_and_persist(
                        workflow_id=workflow_id,
                        request=request,
                        response=response,
                        agent_outputs_snapshot=response_agent_outputs,
                        correlation_id=request.correlation_id,
                    )
                    response.markdown_export = md_info
                except Exception as md_error:
                    error_msg = str(md_error)
                    logger.warning(
                        f"Markdown export failed for workflow {workflow_id}: {error_msg}"
                    )
                    response.markdown_export = {
                        "error": "Export failed",
                        "message": error_msg,
                        "export_timestamp": datetime.now(timezone.utc).isoformat(),
                    }

            # ----------------------------------------------------------------
            # Persist workflow results to database (best-effort, via service)
            # ----------------------------------------------------------------
            try:
                await self._persistence_service.persist_success(
                    request=request,
                    response=response,
                    workflow_id=workflow_id,
                    original_execution_config=original_execution_config,
                )
            except Exception as persist_error:
                logger.error(
                    f"Failed to persist workflow {workflow_id}: {persist_error}"
                )

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

            logger.info(
                f"Workflow {workflow_id} completed successfully in {execution_time:.2f}s"
            )
            return response

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Workflow {workflow_id} failed after {execution_time:.2f}s: {e}"
            )

            error_response = WorkflowResponse(
                workflow_id=workflow_id,
                status="failed",
                agent_outputs={},
                execution_time_seconds=execution_time,
                correlation_id=request.correlation_id,
                error_message=str(e),
            )

            # Persist failed workflow (best-effort, via service)
            try:
                await self._persistence_service.persist_failure(
                    request=request,
                    response=error_response,
                    workflow_id=workflow_id,
                    error_message=str(e),
                    original_execution_config=original_execution_config,
                )
            except Exception as persist_error:
                logger.warning(
                    f"Failed to persist FAILED workflow {workflow_id}: {persist_error}"
                )

            if workflow_id in self._active_workflows:
                self._active_workflows[workflow_id].update(
                    {
                        "status": "failed",
                        "response": error_response,
                        "error": str(e),
                        "end_time": time.time(),
                    }
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

        Uses the in-memory _active_workflows store and a simple heuristic.
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
        Cancel a running workflow (soft-cancel only).
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

            # History loading is still done directly here; this is read-only.
            from OSSS.ai.database.repositories.question_repository import QuestionRepository

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
