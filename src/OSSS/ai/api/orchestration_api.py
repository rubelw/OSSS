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
        self._session_factory = get_session_factory()

        # Optional "repository factory" session manager used for historian
        # document persistence (markdown export).
        self._db_session_factory: Optional[DatabaseSessionFactory] = None

        # -------------------------------------------------------------------
        # Query profile idempotency (prevents double LLM calls)
        # -------------------------------------------------------------------
        self._query_profile_cache: Dict[str, Dict[str, Any]] = {}   # workflow_id -> query_profile dict
        self._query_profile_locks: Dict[str, asyncio.Lock] = {}     # workflow_id -> lock


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
            agent_output_meta={"_routing": {"source": "direct_llm", "final_agents": []}},
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

            model_path = config.get("classifier_model_path") or "models/intent_classifier.joblib"
            model_version = config.get("classifier_model_version") or "v1"

            agent = SklearnIntentClassifierAgent(
                model_path=model_path,
                model_version=model_version,
            )

            out = await agent.run(query, config)
            logger.info(
                "[api] classifier output",
                extra={
                    "workflow_id": config.get("workflow_id"),
                    "correlation_id": config.get("correlation_id"),
                    "classifier": out,
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
        (This is what execute_workflow delegates to.)

        OPTION A APPLIED:
        - No "direct LLM bypass" when request.agents is empty
        - Always injects "classifier" as the first agent in the orchestrator run
        """
        workflow_id = str(uuid.uuid4())
        start_time = time.time()

        original_execution_config = request.execution_config or {}
        config = dict(original_execution_config)
        config["workflow_id"] = workflow_id
        if request.correlation_id:
            config["correlation_id"] = request.correlation_id

        classifier_out = await self._run_classifier_first(request.query, config)

        try:
            logger.info(
                f"Starting workflow {workflow_id} with query: {request.query[:100]}..."
            )

            await emit_workflow_started(
                workflow_id=workflow_id,
                query=request.query,
                agents=request.agents,
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

            # Build orchestrator execution config (copy to avoid mutating request)
            config: Dict[str, Any] = dict(original_execution_config)

            if request.correlation_id:
                config["correlation_id"] = request.correlation_id

            config["workflow_id"] = workflow_id

            # ----------------------------------------------------------------
            # Routing (NO preflight query analysis)
            # ----------------------------------------------------------------
            if request.agents is not None:
                # caller explicitly provided agents (even empty list)
                config["agents"] = list(request.agents)
                config["routing_source"] = "caller"
            elif isinstance(config.get("agents"), list) and config["agents"]:
                config["routing_source"] = "execution_config"
            else:
                config["agents"] = ["refiner", "critic", "historian", "synthesis"]
                config["routing_source"] = "default"

            # ----------------------------------------------------------------
            # ✅ Fix: classifier is a PRE-STEP, not a LangGraph node
            # ----------------------------------------------------------------
            requested = list(config.get("agents") or [])
            if not requested:
                requested = ["refiner", "critic", "historian", "synthesis"]

            # Ensure classifier is NOT part of the LangGraph graph build
            config["agents"] = [a for a in requested if a != "classifier"]

            # Classifier runs as a pre-step (NOT a LangGraph node).
            # Persist result into config so downstream agents can use it if they want.
            config["classifier"] = classifier_out
            config["routing_source"] = (
                f"{config.get('routing_source', 'unknown')}_with_classifier_prestep"
            )

            logger.info(
                "Execution config received",
                extra={
                    "workflow_id": workflow_id,
                    "raw_execution_config": original_execution_config,
                    "routing_source": config.get("routing_source"),
                    "agents": config.get("agents"),
                },
            )

            if self._orchestrator is None:
                raise RuntimeError("Orchestrator not initialized")

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
                    },
                )

                result_context = await self._orchestrator.run(request.query, config)

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

            executed_agents: List[str] = []
            try:
                ao = getattr(result_context, "agent_outputs", {}) or {}
                if isinstance(ao, dict):
                    executed_agents = list(ao.keys())
            except Exception:
                executed_agents = []

            if not executed_agents and structured_outputs:
                executed_agents = list(structured_outputs.keys())

            agent_outputs_to_serialize: Dict[str, Any] = {}
            raw_agent_outputs: Dict[str, Any] = {}
            try:
                raw_agent_outputs = getattr(result_context, "agent_outputs", {}) or {}
                if not isinstance(raw_agent_outputs, dict):
                    raw_agent_outputs = {}
            except Exception:
                raw_agent_outputs = {}

            for agent_name in executed_agents:
                if agent_name in structured_outputs:
                    agent_outputs_to_serialize[agent_name] = structured_outputs[agent_name]
                else:
                    agent_outputs_to_serialize[agent_name] = raw_agent_outputs.get(agent_name, "")

            serialized_agent_outputs = self._convert_agent_outputs_to_serializable(
                agent_outputs_to_serialize
            )

            # ----------------------------------------------------------------
            # Output meta extraction + ensure `action`
            # ----------------------------------------------------------------
            agent_output_meta: Dict[str, Any] = {}
            try:
                aom = exec_state.get("agent_output_meta", {})
                if isinstance(aom, dict):
                    agent_output_meta = aom
            except Exception:
                agent_output_meta = {}

            agent_output_meta["_routing"] = {
                "source": config.get("routing_source", "unknown"),
                "selected_workflow_id": config.get("selected_workflow_id"),
                "final_agents": config.get("agents"),
                "pre_agents": config.get("pre_agents", []),

            }

            # also optionally
            agent_output_meta["_classifier"] = classifier_out

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
                agent_outputs=serialized_agent_outputs,
                execution_time_seconds=execution_time,
                correlation_id=request.correlation_id,
                agent_output_meta=agent_output_meta,
            )

            # ----------------------------------------------------------------
            # Optional markdown export (kept as-is)
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
                        topic_analysis = await topic_manager.analyze_and_suggest_topics(
                            query=request.query,
                            agent_outputs=serialized_agent_outputs,
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
                        agent_outputs=serialized_agent_outputs,
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

                        if db_session_factory:
                            async with db_session_factory.get_repository_factory() as repo_factory:
                                doc_repo = repo_factory.historian_documents

                                with open(md_path_obj, "r", encoding="utf-8") as md_file:
                                    markdown_content = md_file.read()

                                topics_list = suggested_topics[:5] if suggested_topics else []

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
                                        "agents_executed": list(getattr(result_context, "agent_outputs", {}).keys()),
                                    },
                                )

                                logger.info(
                                    f"Workflow {workflow_id} markdown persisted to database: {md_path_obj.name}"
                                )
                        else:
                            logger.warning(
                                f"Database not available, skipping markdown persistence for workflow {workflow_id}"
                            )

                    except Exception as db_persist_error:
                        logger.error(
                            f"Failed to persist markdown to database for workflow {workflow_id}: {db_persist_error}"
                        )

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

            await self._persist_failed_workflow_to_database(
                request, error_response, workflow_id, str(e), original_execution_config
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
        if self._db_session_factory is None:
            try:
                self._db_session_factory = DatabaseSessionFactory()
                await self._db_session_factory.initialize()
                logger.info("Database session factory initialized for markdown persistence")
            except Exception as e:
                logger.warning(f"Failed to initialize database session factory: {e}")
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
        try:
            async with self._session_factory() as session:
                question_repo = QuestionRepository(session)

                execution_metadata = {
                    "workflow_id": workflow_id,
                    "execution_time_seconds": response.execution_time_seconds,
                    "agent_outputs": response.agent_outputs,
                    "agents_requested": request.agents or ["refiner", "critic", "historian", "synthesis"],
                    "export_md": (request.export_md if request.export_md is not None else False),
                    "execution_config": original_execution_config,
                    "api_version": self.api_version,
                    "orchestrator_type": "langgraph-real",
                }

                nodes_executed = list(response.agent_outputs.keys()) if response.agent_outputs else []

                await question_repo.create_question(
                    query=request.query,
                    correlation_id=request.correlation_id,
                    execution_id=workflow_id,
                    nodes_executed=nodes_executed,
                    execution_metadata=execution_metadata,
                )

                logger.info(f"Workflow {workflow_id} persisted to database")

        except Exception as e:
            logger.error(f"Failed to persist workflow {workflow_id}: {e}")

    async def _persist_failed_workflow_to_database(
        self,
        request: WorkflowRequest,
        response: WorkflowResponse,
        workflow_id: str,
        error_message: str,
        original_execution_config: Dict[str, Any],
    ) -> None:
        try:
            async with self._session_factory() as session:
                question_repo = QuestionRepository(session)

                execution_metadata = {
                    "workflow_id": workflow_id,
                    "execution_time_seconds": response.execution_time_seconds,
                    "agent_outputs": response.agent_outputs,
                    "agents_requested": request.agents or ["refiner", "critic", "historian", "synthesis"],
                    "export_md": (request.export_md if request.export_md is not None else False),
                    "execution_config": original_execution_config,
                    "api_version": self.api_version,
                    "orchestrator_type": "langgraph-real",
                    "status": "failed",
                    "error_message": error_message,
                }

                nodes_executed = list(response.agent_outputs.keys()) if response.agent_outputs else []

                await question_repo.create_question(
                    query=request.query,
                    correlation_id=request.correlation_id,
                    execution_id=workflow_id,
                    nodes_executed=nodes_executed,
                    execution_metadata=execution_metadata,
                )

                logger.info(f"Failed workflow {workflow_id} persisted to database")

        except Exception as e:
            logger.error(f"Failed to persist failed workflow {workflow_id}: {e}")

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
            async with self._session_factory() as session:
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
