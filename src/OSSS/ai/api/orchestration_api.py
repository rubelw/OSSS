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
import uuid  # Unique workflow IDs (UUID4)
import asyncio  # Async primitives (sleep, cancellation patterns)
import time  # Wall-clock timing for execution durations
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone  # UTC timestamps for telemetry/metadata
from collections.abc import Mapping, Sequence

import os

# ---------------------------------------------------------------------------
# OSSS core context / orchestration
# ---------------------------------------------------------------------------

from OSSS.ai.context import AgentContext

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
    WorkflowRequest,  # Input request model for workflow execution
    WorkflowResponse,  # Output response model for workflow execution
    StatusResponse,  # Response model for status polling
    SkippedAgentOutput,  # NEW
)
from OSSS.ai.api.base import APIHealthStatus  # API-level health response model
from OSSS.ai.diagnostics.health import HealthStatus  # Health enum: HEALTHY/DEGRADED/UNHEALTHY

# Decorator that ensures initialize() has been called before API methods run
from OSSS.ai.api.decorators import ensure_initialized

# The production orchestrator that actually runs the LangGraph pipeline
from OSSS.ai.orchestration.orchestrator import LangGraphOrchestrator

# Observability helpers (structured logger)
from OSSS.ai.observability import get_logger

# Workflow lifecycle events (for metrics/traces/audit logs)
from OSSS.ai.events import emit_workflow_started, emit_workflow_completed

# Database / persistence infrastructure (used via helpers/services)
from OSSS.ai.database.session_factory import (
    DatabaseSessionFactory,
    get_database_session_factory,
)
from OSSS.ai.database.models import ConversationState  # or ConversationStateModel

from OSSS.ai.orchestration.models_internal import (
    AgentOutputEnvelope,
    RoutingMeta,
    WorkflowResult,
)

# Module-level logger (structured)
logger = get_logger(__name__)


def _normalize_agent_channel_key(channel_key: str) -> str:
    """
    Map structured_outputs keys like 'data_query:students' back to the logical
    agent name ('data_query') for the public API.
    """
    if not isinstance(channel_key, str):
        return str(channel_key)
    return channel_key.split(":", 1)[0] or channel_key


def _detect_skipped_output_from_payload(payload: Any) -> Optional[SkippedAgentOutput]:
    """
    Detect a 'skipped' agent output from the internal payload and convert it
    into a SkippedAgentOutput envelope for the external API.

    We look for:
      - meta.reason == 'skip_non_structured'
      - meta.event  == 'data_query_skip_non_structured'
    but you can widen this as needed.
    """
    if payload is None:
        return None

    # Canonical_output shape from DataQueryAgent:
    # {
    #   "table_markdown": "",
    #   "markdown": "",
    #   "meta": {
    #       "reason": "skip_non_structured",
    #       "event": "data_query_skip_non_structured",
    #       "projection_mode": "none",
    #   },
    #   "action": "noop",
    #   "intent": "none",
    # }
    if isinstance(payload, dict):
        meta = payload.get("meta") or {}
        reason = meta.get("reason")
        event = meta.get("event")
        if (
            isinstance(reason, str)
            and reason == "skip_non_structured"
            and isinstance(event, str)
            and event == "data_query_skip_non_structured"
        ):
            return SkippedAgentOutput(
                status="skipped",
                reason=reason,
                action=meta.get("action") or payload.get("action") or "noop",
                intent=meta.get("intent") or payload.get("intent") or "none",
                meta=meta,
            )

    # Not a recognized skip envelope
    return None


def _build_agent_outputs_for_response(
    execution_state: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build the public agent_outputs dict for WorkflowResponse.

    - Uses execution_state["structured_outputs"] when present.
    - Detects 'skipped' payloads and wraps them in SkippedAgentOutput.
    - Falls back to basic string outputs if structured outputs are missing.
    """
    agent_outputs: Dict[str, Any] = {}

    structured_outputs = execution_state.get("structured_outputs") or {}

    # Prefer structured_outputs if available
    if isinstance(structured_outputs, dict) and structured_outputs:
        for channel_key, payload in structured_outputs.items():
            agent_name = _normalize_agent_channel_key(channel_key)

            # Option 2: explicit skipped envelope
            skipped = _detect_skipped_output_from_payload(payload)
            if skipped is not None:
                # Keep one entry per logical agent; last one wins if multiple channels
                agent_outputs[agent_name] = skipped
                continue

            # Otherwise, keep payload as-is (dict / string / pydantic model)
            agent_outputs[agent_name] = payload

        return agent_outputs

    # Fallback: if you also store "agent_outputs" somewhere else as plain strings
    raw_agent_outputs = execution_state.get("agent_outputs") or {}
    if isinstance(raw_agent_outputs, dict):
        for agent_name, output in raw_agent_outputs.items():
            # Nothing fancy here; Option 2 is handled only via structured_outputs
            agent_outputs[agent_name] = output

    return agent_outputs


# ---------------------------------------------------------------------------
# Conversation / thread helpers (Option B)
# ---------------------------------------------------------------------------


def _generate_conversation_id() -> str:
    """
    Generate a stable, OSSS-style conversation/thread ID.

    This is used when the client does NOT provide a conversation_id.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"osss_{ts}_{suffix}"


def _resolve_conversation_id(request: WorkflowRequest) -> str:
    """
    Option B: Prefer an explicit conversation_id from the client, otherwise
    generate a new one and return it.

    Priority:
      1) request.conversation_id (if the model has it)
      2) request.execution_config["conversation_id"]
      3) auto-generated OSSS conversation_id
    """
    # 1) Explicit field on the request model
    conv_id = getattr(request, "conversation_id", None)
    if isinstance(conv_id, str) and conv_id.strip():
        return conv_id.strip()

    # 2) Nested in execution_config
    exec_cfg = request.execution_config or {}
    if isinstance(exec_cfg, dict):
        conv_id = exec_cfg.get("conversation_id")
        if isinstance(conv_id, str) and conv_id.strip():
            return conv_id.strip()

    # 3) Fallback: generate a new one
    new_id = _generate_conversation_id()
    logger.info(
        "Auto-generated conversation_id",
        extra={
            "event": "conversation_id.auto_generated",
            "conversation_id": new_id,
        },
    )
    return new_id


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


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


def _executed_agents_from_context(
    ctx: AgentContext | Any,
    exec_state: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Best-effort list of agents that produced outputs in this workflow.

    Priority:
      1) exec_state["successful_agents"] if present (node_wrappers fastpath)
      2) ctx.successful_agents if present on AgentContext
      3) ctx.agent_outputs keys
      4) ctx.output_envelopes logical_name / agent_name

    NOTE: For (1) and (2) we normalize to lowercase/strip to match
    node_wrappers._merge_successful_agents semantics; for (3) and (4)
    we preserve keys as-is, since they may be full names like
    "data_query:wizard:consents".
    """
    agents: list[str] = []

    def _add(name: Any, *, lower: bool = False) -> None:
        if name is None:
            return
        s = str(name).strip()
        if not s:
            return
        if lower:
            s = s.lower()
        if s not in agents:
            agents.append(s)

    # 1) From execution_state.successful_agents (may be list/set/tuple)
    if isinstance(exec_state, Mapping):
        succ = exec_state.get("successful_agents")
        if isinstance(succ, (list, set, tuple)):
            for a in succ:
                _add(a, lower=True)

    # 2) From AgentContext.successful_agents
    if hasattr(ctx, "successful_agents"):
        try:
            succ_ctx = getattr(ctx, "successful_agents")
        except Exception:
            succ_ctx = None
        if isinstance(succ_ctx, (list, set, tuple)):
            for a in succ_ctx:
                _add(a, lower=True)

    # 3) From direct agent_outputs mapping
    direct_outputs: Optional[Mapping[str, Any]] = None

    if isinstance(ctx, Mapping):
        direct_outputs = ctx.get("agent_outputs")  # type: ignore[index]

    if direct_outputs is None and hasattr(ctx, "agent_outputs"):
        direct_outputs = getattr(ctx, "agent_outputs")

    if isinstance(direct_outputs, Mapping):
        for agent in direct_outputs.keys():
            _add(agent, lower=False)

    # 4) From canonical envelopes (new AgentContext API)
    if hasattr(ctx, "output_envelopes"):
        try:
            envs = getattr(ctx, "output_envelopes") or []
        except Exception:
            envs = []

        for env in envs:
            if isinstance(env, Mapping):
                logical = env.get("logical_name")
                agent = env.get("agent_name") or env.get("agent")
            else:
                logical = getattr(env, "logical_name", None)
                agent = getattr(env, "agent_name", None) or getattr(env, "agent", None)

            for name in (logical, agent):
                _add(name, lower=False)

    return agents


def _db_persist_enabled() -> bool:
    return os.getenv("OSSS_AI_DB_PERSIST_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


# ---------------------------------------------------------------------------
# Main Orchestration API implementation
# ---------------------------------------------------------------------------


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
        # _session_factory is a *callable* returning an async context manager
        # (DatabaseSessionFactory.get_session), to keep the same shape that
        # WorkflowPersistenceService and history loaders expect.
        self._session_factory = None  # type: ignore[assignment]
        self._db_session_factory: Optional[DatabaseSessionFactory] = None

        # -------------------------------------------------------------------
        # Persistence service (delegated DB writes)
        # -------------------------------------------------------------------
        # Use the default provider (get_database_session_factory), which returns
        # a DatabaseSessionFactory instance. WorkflowPersistenceService will then
        # call .is_initialized / .initialize() on that instance directly.
        self._persistence_service = persistence_service or WorkflowPersistenceService(
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
        Provider used by WorkflowPersistenceService and other DB helpers.

        Returns:
            Callable[[], AsyncContextManager[AsyncSession]] | None

        The returned callable is typically DatabaseSessionFactory.get_session,
        so callers can do:

            sf = session_factory_provider()
            async with sf() as session:
                ...
        """
        if not _db_persist_enabled():
            # Keep this quiet; callers may check often
            logger.debug("DB persistence disabled; session factory unavailable")
            return None

        if self._session_factory is None:
            # Use the shared global DatabaseSessionFactory instance
            factory = get_database_session_factory()
            # We assume initialization was done at app startup via
            # initialize_database_session_factory(). If not, get_session()
            # will raise and the persistence layer will treat it as best-effort.
            self._db_session_factory = factory
            self._session_factory = factory.get_session

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
    # Conversation / wizard state persistence
    # -----------------------------------------------------------------------

    async def _load_conversation_state(self, conversation_id: str) -> Dict[str, Any]:
        """Load persisted conversation state from the database."""

        logger.debug(
            "Loading conversation state...",
            extra={
                "event": "conversation_state.load.start",
                "conversation_id": conversation_id,
            },
        )

        db_factory = await self._get_or_create_db_session_factory()
        if db_factory is None:
            logger.warning(
                "DB session factory unavailable — returning empty conversation state",
                extra={
                    "event": "conversation_state.load.skipped",
                    "conversation_id": conversation_id,
                },
            )
            return {}

        try:
            async with db_factory.get_session() as session:
                row = await session.get(ConversationState, conversation_id)

                if not row:
                    logger.debug(
                        "No conversation state found (new conversation)",
                        extra={
                            "event": "conversation_state.load.none",
                            "conversation_id": conversation_id,
                        },
                    )
                    return {}

                if not isinstance(row.state, dict):
                    logger.warning(
                        "Conversation state was stored but is not a dict — returning empty state",
                        extra={
                            "event": "conversation_state.load.invalid",
                            "conversation_id": conversation_id,
                            "type": type(row.state).__name__,
                        },
                    )
                    return {}

                # 🔁 Migration shim: normalize legacy "wizard_state" to "wizard"
                state: Dict[str, Any] = dict(row.state or {})
                if "wizard_state" in state and "wizard" not in state:
                    wizard_state = state.get("wizard_state")
                    if isinstance(wizard_state, dict):
                        state["wizard"] = wizard_state

                logger.debug(
                    "Conversation state loaded successfully",
                    extra={
                        "event": "conversation_state.load.success",
                        "conversation_id": conversation_id,
                        "state_keys": list(state.keys()),
                        "state_size_bytes": len(str(state).encode("utf-8")),
                    },
                )
                return state

        except Exception as e:
            logger.error(
                f"Failed to load conversation state: {e}",
                extra={
                    "event": "conversation_state.load.error",
                    "conversation_id": conversation_id,
                    "error_type": type(e).__name__,
                },
            )
            return {}

    async def _save_conversation_state(
        self, conversation_id: str, state: Dict[str, Any]
    ) -> None:
        """Persist conversation state to the database."""

        logger.debug(
            "Saving conversation state...",
            extra={
                "event": "conversation_state.save.start",
                "conversation_id": conversation_id,
                "state_size_bytes": len(str(state).encode("utf-8")) if state else 0,
            },
        )

        db_factory = await self._get_or_create_db_session_factory()
        if db_factory is None:
            logger.warning(
                "DB session factory unavailable — conversation state NOT persisted.",
                extra={
                    "event": "conversation_state.save.skipped",
                    "conversation_id": conversation_id,
                },
            )
            return

        try:
            async with db_factory.get_session() as session:
                existing = await session.get(ConversationState, conversation_id)

                if existing is None:
                    logger.info(
                        "Creating new conversation state record",
                        extra={
                            "event": "conversation_state.save.insert",
                            "conversation_id": conversation_id,
                            "keys": list(state.keys()) if state else [],
                        },
                    )
                    session.add(
                        ConversationState(conversation_id=conversation_id, state=state)
                    )
                else:
                    logger.debug(
                        "Updating existing conversation state record",
                        extra={
                            "event": "conversation_state.save.update",
                            "conversation_id": conversation_id,
                            "updated_keys": list(state.keys()) if state else [],
                        },
                    )
                    existing.state = state

            logger.debug(
                "Conversation state saved successfully",
                extra={
                    "event": "conversation_state.save.success",
                    "conversation_id": conversation_id,
                },
            )

        except Exception as e:
            logger.error(
                f"Failed to save conversation state: {e}",
                extra={
                    "event": "conversation_state.save.error",
                    "conversation_id": conversation_id,
                    "error_type": type(e).__name__,
                },
            )
            raise

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
                    failed_executions = orchestrator_stats.get(
                        "failed_executions", 0
                    )

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

    # -----------------------------------------------------------------------
    # Agent outputs helpers (using new AgentContext)
    # -----------------------------------------------------------------------

    def _build_envelopes_from_context(self, ctx: AgentContext | Any) -> list[AgentOutputEnvelope]:
        """
        Build a normalized list[AgentOutputEnvelope] from the AgentContext.

        Priority:
        1) ctx.output_envelopes (canonical public property on AgentContext)
        2) ctx.agent_output_envelopes / ctx._agent_output_envelopes
        3) Fallback: synthesize envelopes from ctx.agent_outputs if needed
        """
        envelopes: list[AgentOutputEnvelope] = []

        raw_candidates: list[Any] = []

        # 1) Canonical property
        if hasattr(ctx, "output_envelopes"):
            try:
                val = getattr(ctx, "output_envelopes")
                if isinstance(val, Sequence) and not isinstance(val, (str, bytes)):
                    raw_candidates = list(val)
            except Exception:
                raw_candidates = []

        # 2) Internal attributes, if canonical is empty
        if not raw_candidates:
            for attr in ("agent_output_envelopes", "_agent_output_envelopes"):
                if not hasattr(ctx, attr):
                    continue
                try:
                    val = getattr(ctx, attr)
                except Exception:
                    continue
                if isinstance(val, Sequence) and not isinstance(val, (str, bytes)):
                    raw_candidates = list(val)
                    break

        # 3) Normalize any envelope-like objects/dicts we found
        for e in raw_candidates:
            if isinstance(e, Mapping):
                agent_name = e.get("agent_name") or e.get("agent") or e.get("agent_id")
                logical_name = e.get("logical_name")
                content = e.get("content") or e.get("output")
                role = e.get("role")
                meta = e.get("meta") or {}
            else:
                agent_name = getattr(e, "agent_name", None) or getattr(e, "agent", None)
                logical_name = getattr(e, "logical_name", None)
                content = getattr(e, "content", None) or getattr(e, "output", None)
                role = getattr(e, "role", None)
                meta = getattr(e, "meta", None) or {}

            if not agent_name:
                continue

            if not logical_name:
                logical_name = str(agent_name).split(":", 1)[0]

            envelopes.append(
                AgentOutputEnvelope(
                    agent_name=str(agent_name),
                    logical_name=str(logical_name),
                    role=role,
                    content=content,
                    meta=dict(meta),
                )
            )

        # 4) Fallback: synthesize from ctx.agent_outputs if we still have none
        if not envelopes:
            direct_outputs: Optional[Mapping[str, Any]] = None

            if isinstance(ctx, Mapping):
                direct_outputs = ctx.get("agent_outputs")  # type: ignore[index]
            if direct_outputs is None and hasattr(ctx, "agent_outputs"):
                direct_outputs = getattr(ctx, "agent_outputs")

            if isinstance(direct_outputs, Mapping):
                for agent_name, content in direct_outputs.items():
                    if agent_name is None:
                        continue
                    agent_name_str = str(agent_name)
                    logical_name = agent_name_str.split(":", 1)[0]
                    envelopes.append(
                        AgentOutputEnvelope(
                            agent_name=agent_name_str,
                            logical_name=logical_name,
                            content=content,
                            meta={},
                        )
                    )

        return envelopes

    def _build_agent_outputs_payload(
        self,
        ctx: AgentContext | Any,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Build agent_outputs (simple agent -> content map) and agent_output_meta
        (full envelope per logical agent) from AgentContext.

        With the new AgentContext:
        - ctx.agent_outputs is already a canonical "last content" map keyed by
          logical name (and sometimes full name).
        - ctx.output_envelopes is the canonical ordered list of envelopes,
          each with:
            - agent_name (full name, e.g. 'data_query:wizard:consents')
            - logical_name (e.g. 'data_query')
            - content
            - meta (intent, wizard state, etc.)
        - ctx.execution_state['agent_output_meta'] may contain previous
          envelope-like dicts; we merge those as a base.

        Additionally, for data_query workflows, some agents (especially
        DataQueryAgent) currently store their output only in
        execution_state["data_query_result"] and/or
        execution_state["structured_outputs"]. This helper now normalizes those
        into agent_outputs/agent_output_meta as well.
        """
        agent_outputs: Dict[str, Any] = {}
        agent_output_meta: Dict[str, Any] = {}

        # ------------------------------------------------------------------
        # 1) Baseline from ctx.agent_outputs
        # ------------------------------------------------------------------
        direct_outputs: Optional[Mapping[str, Any]] = None

        if isinstance(ctx, Mapping):
            direct_outputs = ctx.get("agent_outputs")  # type: ignore[index]

        if direct_outputs is None and hasattr(ctx, "agent_outputs"):
            direct_outputs = getattr(ctx, "agent_outputs")

        if isinstance(direct_outputs, Mapping):
            for agent_name, content in direct_outputs.items():
                if content is None:
                    continue
                name = str(agent_name)
                agent_outputs[name] = content
                # minimal meta; will be enriched below
                agent_output_meta.setdefault(name, {"agent": name, "content": content})

        # ------------------------------------------------------------------
        # 2) Seed meta from execution_state.agent_output_meta (if present)
        # ------------------------------------------------------------------
        exec_state = getattr(ctx, "execution_state", {}) or {}
        if isinstance(exec_state, Mapping):
            raw_meta = exec_state.get("agent_output_meta") or {}
            if isinstance(raw_meta, Mapping):
                for logical_name, env in raw_meta.items():
                    if not logical_name:
                        continue
                    lname = str(logical_name)
                    if isinstance(env, Mapping):
                        meta = dict(env)
                    else:
                        meta = {"agent": lname, "content": env}
                    agent_output_meta.setdefault(lname, meta)
                    # If meta contains a more precise content, prefer it
                    content = meta.get("content")
                    if content is not None:
                        agent_outputs[lname] = content

            # ------------------------------------------------------------------
            # 2b) NEW: bridge data_query-specific fields into agent_outputs
            # ------------------------------------------------------------------

            # (a) Single result: execution_state["data_query_result"]
            dq_result = exec_state.get("data_query_result")
            if dq_result is not None and "data_query" not in agent_outputs:
                logical_name = "data_query"
                agent_outputs[logical_name] = dq_result

                existing_meta = agent_output_meta.get(logical_name, {})
                if not isinstance(existing_meta, dict):
                    existing_meta = {}

                new_meta = dict(existing_meta)
                new_meta.setdefault("agent", logical_name)
                new_meta.setdefault("logical_name", logical_name)
                new_meta.setdefault("content", dq_result)
                new_meta.setdefault("source", "execution_state.data_query_result")

                agent_output_meta[logical_name] = new_meta

            # (b) Structured outputs: execution_state["structured_outputs"]
            structured_outputs = exec_state.get("structured_outputs")
            if isinstance(structured_outputs, Mapping):
                for logical_name, content in structured_outputs.items():
                    if content is None:
                        continue
                    lname = str(logical_name)

                    # Avoid clobbering more specific content already present
                    if lname not in agent_outputs:
                        agent_outputs[lname] = content

                    existing_meta = agent_output_meta.get(lname, {})
                    if not isinstance(existing_meta, dict):
                        existing_meta = {}

                    new_meta = dict(existing_meta)
                    new_meta.setdefault("agent", lname)
                    new_meta.setdefault("logical_name", lname)
                    new_meta.setdefault("content", content)
                    new_meta.setdefault("source", "execution_state.structured_outputs")

                    agent_output_meta[lname] = new_meta

        # ------------------------------------------------------------------
        # 3) Overlay canonical envelopes from ctx.output_envelopes
        # ------------------------------------------------------------------
        envelopes: list[Any] = []
        if hasattr(ctx, "output_envelopes"):
            try:
                raw_envs = getattr(ctx, "output_envelopes") or []
                # raw_envs is a list[dict] from AgentOutputEnvelope.as_public_dict()
                if isinstance(raw_envs, Sequence) and not isinstance(
                    raw_envs, (str, bytes)
                ):
                    envelopes = list(raw_envs)
            except Exception:
                envelopes = []

        for env in envelopes:
            # dict-like (preferred)
            if isinstance(env, Mapping):
                logical = env.get("logical_name")
                full_agent = env.get("agent_name") or env.get("agent")
                content = env.get("content")
                meta = env.get("meta") or {}
            else:
                # object-like (defensive)
                logical = getattr(env, "logical_name", None)
                full_agent = getattr(env, "agent_name", None) or getattr(
                    env, "agent", None
                )
                content = getattr(env, "content", None)
                meta = getattr(env, "meta", None) or {}

            if not logical and full_agent:
                logical = str(full_agent).split(":", 1)[0]

            if not logical:
                continue

            logical_name = str(logical)

            # Update agent_outputs with canonical content
            if content is not None:
                agent_outputs[logical_name] = content

            # Merge/overlay meta
            existing_meta = agent_output_meta.get(logical_name, {})
            if not isinstance(existing_meta, dict):
                existing_meta = {}

            new_meta = dict(existing_meta)
            if isinstance(meta, Mapping):
                new_meta.update(meta)

            new_meta.setdefault("agent", full_agent or logical_name)
            new_meta.setdefault("logical_name", logical_name)
            new_meta.setdefault("content", content)

            agent_output_meta[logical_name] = new_meta

        logger.debug(
            "[orchestration_api] agent_outputs payload built",
            extra={
                "event": "agent_outputs_payload_built",
                "keys": list(agent_outputs.keys()),
                "has_data_query": "data_query" in agent_outputs,
                "has_structured_outputs": isinstance(
                    getattr(ctx, "execution_state", {}) or {}, Mapping
                )
                and bool(
                    (getattr(ctx, "execution_state", {}) or {}).get(
                        "structured_outputs"
                    )
                ),
            },
        )

        return agent_outputs, agent_output_meta

    def _select_final_answer(
        self,
        agent_outputs: Dict[str, Any],
        graph_pattern: str | None = None,
        agent_output_meta: Optional[Dict[str, Any]] = None,
        routing_meta: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Any, Optional[str]]:
        """
        Decide which agent's output becomes the top-level `answer`.

        Returns:
            (final_answer, final_answer_agent_name)
        """
        graph_pattern = (graph_pattern or "").strip().lower()

        # 1) Special handling for data_query workflows (Option A)
        if graph_pattern == "data_query":
            # Prefer collapsed 'data_query' key if present
            if "data_query" in agent_outputs:
                return agent_outputs["data_query"], "data_query"

            # Otherwise, prefer wizard-style keys like 'data_query:wizard:...'
            for agent_name, content in agent_outputs.items():
                if isinstance(agent_name, str) and agent_name.startswith(
                    "data_query:"
                ):
                    return content, agent_name

        # 2) Generic preferences for any pattern
        if "final" in agent_outputs:
            return agent_outputs["final"], "final"

        # In older/custom graphs with a synthesis node acting as final
        if "synthesis" in agent_outputs:
            return agent_outputs["synthesis"], "synthesis"

        if "refiner" in agent_outputs:
            return agent_outputs["refiner"], "refiner"

        # 3) Last resort: first available output, if any
        if agent_outputs:
            agent_name, content = next(iter(agent_outputs.items()))
            return content, agent_name

        # 4) Nothing available
        return "", None

    # -----------------------------------------------------------------------
    # Public execution entrypoint
    # -----------------------------------------------------------------------

    @ensure_initialized
    async def execute_workflow(self, request: WorkflowRequest) -> WorkflowResponse:
        """
        Execute a workflow using the production orchestrator.

        Intentionally a thin async wrapper around _execute_workflow_async.
        """
        return await self._execute_workflow_async(request)

    async def _execute_workflow_async(
        self, request: WorkflowRequest
    ) -> WorkflowResponse:
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
        correlation_id = request.correlation_id or f"req-{uuid.uuid4()}"

        # 🔑 Stable conversation identifier for continuity across turns (Option B)
        conversation_id: str = _resolve_conversation_id(request)

        # NEW: restore any per-conversation state (wizard, classifications, etc.)
        restored_conversation_state: Dict[str, Any] = {}
        if conversation_id:
            try:
                restored_conversation_state = (
                    await self._load_conversation_state(conversation_id)
                ) or {}
            except Exception as conv_exc:
                logger.warning(
                    "[orchestration_api] Failed to load conversation state",
                    extra={
                        "event": "conversation_state_load_failed",
                        "conversation_id": conversation_id,
                        "error": str(conv_exc),
                    },
                )

        # Ensure classifier_profile is always defined in this scope
        classifier_profile: Dict[str, Any] | None = None

        # Normalize request.agents to a list; do NOT override/invent agents here.
        request.agents = _norm_agents(request.agents)

        # Immutable snapshot of the caller-provided execution_config
        original_execution_config = request.execution_config or {}
        if not isinstance(original_execution_config, dict):
            original_execution_config = {}

        # Base config passed into orchestrator; only meta fields added here.
        config: Dict[str, Any] = dict(original_execution_config)
        config["workflow_id"] = workflow_id
        config["correlation_id"] = correlation_id

        # Seed execution_state so the classifier and orchestrator share it
        execution_state: Dict[str, Any] = dict(
            original_execution_config.get("execution_state") or {}
        )

        # NEW: merge in any restored per-conversation state (wizard, etc.)
        if restored_conversation_state:
            execution_state.update(restored_conversation_state)

        # 🔑 Ensure conversation_id is visible in execution_state (authoritative)
        execution_state["conversation_id"] = conversation_id

        config["execution_state"] = execution_state

        # 🔑 Tell the orchestrator/memory manager which thread to use
        config["thread_id"] = conversation_id

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

        # Ensure exec_state is always defined, even if an early exception occurs
        exec_state: Dict[str, Any] = {}

        try:
            logger.info(
                f"Starting workflow {workflow_id} with query: {request.query[:100]}...",
                extra={
                    "conversation_id": conversation_id,
                    "correlation_id": correlation_id,
                },
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
                correlation_id=correlation_id,
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
                from OSSS.ai.orchestration.advanced_adapter import (
                    AdvancedOrchestratorAdapter,
                )

                logger.info(
                    "[api] Delegating to AdvancedOrchestratorAdapter",
                    extra={
                        "workflow_id": workflow_id,
                        "correlation_id": correlation_id,
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
                        "correlation_id": correlation_id,
                        "conversation_id": conversation_id,
                        "caller_agents": agents_for_event,
                        "graph_pattern": original_execution_config.get(
                            "graph_pattern"
                        ),
                    },
                )

                result_context = await self._orchestrator.run(request.query, config)

            # 🔍 DEBUG: basic introspection on result_context
            try:
                rc_agent_outputs = getattr(result_context, "agent_outputs", None)
                rc_state = getattr(result_context, "execution_state", None)

                logger.debug(
                    "[orchestration_api] result_context introspection",
                    extra={
                        "event": "result_context_introspection",
                        "result_context_type": type(result_context).__name__,
                        "has_agent_outputs_attr": rc_agent_outputs is not None,
                        "agent_outputs_type": type(rc_agent_outputs).__name__
                        if rc_agent_outputs is not None
                        else None,
                        "agent_outputs_keys": list(rc_agent_outputs.keys())
                        if isinstance(rc_agent_outputs, Mapping)
                        else None,
                        "has_state_attr": rc_state is not None,
                        "state_type": type(rc_state).__name__
                        if rc_state is not None
                        else None,
                        "state_keys": list(rc_state.keys())
                        if isinstance(rc_state, Mapping)
                        else None,
                    },
                )
            except Exception as debug_exc:
                logger.debug(
                    "[orchestration_api] result_context introspection failed",
                    extra={"error": str(debug_exc)},
                )

            execution_time = time.time() - start_time

            # ----------------------------------------------------------------
            # Normalize execution_state & routing metadata
            # ----------------------------------------------------------------
            exec_state = {}
            try:
                maybe_state = getattr(result_context, "execution_state", None)
                if isinstance(maybe_state, dict):
                    exec_state = maybe_state
            except Exception:
                exec_state = {}

            # NEW: persist wizard-related state for this conversation (if any)
            try:
                persisted_conversation_id = conversation_id  # authoritative now

                # Prefer the *final* execution_state from the workflow result,
                # fall back to any earlier exec_state only if needed.
                result_exec_state = (
                        getattr(result_context, "execution_state", None) or {}
                )
                base_exec_state = exec_state or {}

                # Merge older + newer, letting the *newer* values win
                state_to_persist: Dict[str, Any] = {
                    **base_exec_state,
                    **result_exec_state,
                }

                # 🔑 Look for wizard state under both modern and legacy keys
                wizard_state = (
                        state_to_persist.get("wizard")
                        or state_to_persist.get("wizard_state")
                )

                minimal_state: Dict[str, Any] = {
                    "classifier_result": (
                            state_to_persist.get("classifier_result")
                            or classifier_profile
                    ),
                    "task_classification": state_to_persist.get(
                        "task_classification"
                    ),
                    "cognitive_classification": state_to_persist.get(
                        "cognitive_classification"
                    ),
                }

                # Only persist wizard if we actually have one
                if isinstance(wizard_state, dict):
                    minimal_state["wizard"] = wizard_state

                await self._save_conversation_state(
                    conversation_id=persisted_conversation_id,
                    state=minimal_state,
                )

            except Exception as conv_exc:
                logger.warning(
                    "[orchestration_api] Failed to persist conversation state",
                    extra={
                        "event": "conversation_state_persist_failed",
                        "error": str(conv_exc),
                    },
                )

            # Which agents actually ran (best-effort)
            executed_agents: List[str] = _executed_agents_from_context(
                result_context, exec_state
            )
            if not isinstance(executed_agents, list):
                executed_agents = []

            routing_source = config.get(
                "routing_source", "caller_with_classifier_prestep"
            )
            planned_agents = exec_state.get("planned_agents") or []
            selected_workflow_id = config.get("selected_workflow_id")
            pre_agents = exec_state.get("pre_agents") or []

            graph_pattern = (
                exec_state.get("graph_pattern")
                or exec_state.get("execution_config", {}).get("graph_pattern")
                or config.get("graph_pattern")
                or original_execution_config.get("graph_pattern")
            )

            routing_meta = {
                "source": routing_source,
                "planned_agents": planned_agents,
                "executed_agents": executed_agents,
                "selected_workflow_id": selected_workflow_id,
                "pre_agents": pre_agents,
                "graph_pattern": graph_pattern,
            }

            # ----------------------------------------------------------------
            # Build *internal* agent_outputs / agent_output_meta from AgentContext
            # ----------------------------------------------------------------
            agent_outputs_internal, agent_output_meta = (
                self._build_agent_outputs_payload(result_context)
            )

            # Attach routing into meta for callers (similar to direct LLM path)
            agent_output_meta["_routing"] = routing_meta

            # Normalize envelopes into internal model
            envelopes: list[AgentOutputEnvelope] = self._build_envelopes_from_context(
                result_context
            )

            # Make internal agent_outputs JSON-serializable for persistence / exports
            agent_outputs_serializable = self._convert_agent_outputs_to_serializable(
                agent_outputs_internal
            )

            # Default markdown_export in case export_md is disabled or fails
            markdown_export = None

            # Decide final answer (prefer wizard output for data_query) using *internal* map
            final_answer, final_answer_agent = self._select_final_answer(
                agent_outputs=agent_outputs_internal,
                graph_pattern=graph_pattern,
                agent_output_meta=agent_output_meta,
                routing_meta=routing_meta,
            )

            # Fallbacks so validator is always happy:
            if not final_answer:
                if "final" in agent_outputs_internal:
                    final_answer_agent = "final"
                    final_answer = agent_outputs_internal["final"]
                elif "data_query:wizard:consents" in agent_outputs_internal:
                    final_answer_agent = "data_query:wizard:consents"
                    final_answer = agent_outputs_internal[final_answer_agent]
                elif agent_outputs_internal:
                    final_answer_agent, final_answer = next(
                        iter(agent_outputs_internal.items())
                    )

            # ----------------------------------------------------------------
            # Build internal WorkflowResult and stash in execution_state
            # ----------------------------------------------------------------
            try:
                routing_model = RoutingMeta(**routing_meta)
                workflow_result = WorkflowResult(
                    query=request.query,
                    graph_pattern=graph_pattern,
                    routing=routing_model,
                    envelopes=envelopes,
                    execution_state=exec_state,
                    final_answer_agent=final_answer_agent,
                    final_answer=final_answer,
                )
                # Store a JSON-serializable view for debugging / analytics
                exec_state["workflow_result"] = workflow_result.model_dump()
            except Exception as wr_exc:
                logger.debug(
                    "[orchestration_api] failed to build WorkflowResult",
                    extra={"error": str(wr_exc)},
                )

            # ----------------------------------------------------------------
            # Build *external* agent_outputs for API response (Option 2)
            #   - uses exec_state["structured_outputs"]
            #   - wraps skips as SkippedAgentOutput
            # ----------------------------------------------------------------
            agent_outputs_for_response = _build_agent_outputs_for_response(exec_state)

            # Decide status
            # Only allowed values: completed | failed | running | cancelled
            status = (
                "completed"
                if (final_answer or agent_outputs_for_response)
                else "failed"
            )

            response = WorkflowResponse(
                workflow_id=workflow_id,
                answer=final_answer,
                execution_state=exec_state,
                status=status,
                agent_output_meta=agent_output_meta,
                agent_outputs=agent_outputs_for_response,
                execution_time_seconds=execution_time,
                correlation_id=correlation_id,
                conversation_id=conversation_id,  # 🔑 Option B: expose to client
                error_message=None if status == "completed" else "No agent outputs",
                markdown_export=markdown_export,
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
                        agent_outputs_snapshot=agent_outputs_serializable,
                        correlation_id=correlation_id,
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
                correlation_id=correlation_id,
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

            # Sanitize exec_state for error response
            safe_exec_state: Dict[str, Any] = {}

            try:
                allowed_keys = {
                    "execution_config",
                    "wizard",  # 🔹 NEW: expose canonical wizard state
                    "wizard_state",
                    "agent_execution_status",
                    "timestamps",
                    "workflow_result",
                    # 🔹 NEW: keep routing/planning info for better persistence + debugging
                    "planned_agents",
                    "agents_to_run",
                    "graph_pattern",
                    "route",
                    "route_key",
                }

                for k, v in (exec_state or {}).items():
                    if k in allowed_keys:
                        safe_exec_state[k] = v

            except Exception:
                safe_exec_state = {}

            error_response = WorkflowResponse(
                workflow_id=workflow_id,
                status="failed",
                agent_outputs={},
                execution_time_seconds=execution_time,
                correlation_id=correlation_id,
                error_message=str(e),
                execution_state=safe_exec_state,
                conversation_id=conversation_id,  # 🔑 keep it stable even on failure
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
                correlation_id=correlation_id,
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
    # Database session factory for markdown & conv state persistence
    # -----------------------------------------------------------------------

    async def _get_or_create_db_session_factory(
        self,
    ) -> Optional[DatabaseSessionFactory]:
        """
        Lazy helper for features that need a DatabaseSessionFactory instance
        (conversation state + markdown export, etc).
        """
        if not _db_persist_enabled():
            logger.debug(
                "DB persistence disabled; markdown/conv-state DB session factory unavailable"
            )
            return None

        if self._db_session_factory is None:
            try:
                # Reuse the shared global factory
                self._db_session_factory = get_database_session_factory()
                if not self._db_session_factory.is_initialized:
                    await self._db_session_factory.initialize()
                logger.info(
                    "Database session factory initialized for markdown/conv-state persistence"
                )
            except Exception as e:
                logger.warning(
                    "Failed to initialize database session factory for markdown/conv-state persistence",
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
                "execution_time": (
                    wf.get("end_time", time.time()) - wf["start_time"]
                ),
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
                logger.debug(
                    "DB persistence disabled; skipping workflow history fetch"
                )
                return []

            # History loading is still done directly here; this is read-only.
            from OSSS.ai.database.repositories.question_repository import (
                QuestionRepository,
            )

            # sf is a callable returning an async context manager
            async with sf() as session:
                question_repo = QuestionRepository(session)
                questions = await question_repo.get_recent_questions(
                    limit=limit, offset=offset
                )

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
    async def get_status_by_correlation_id(
        self, correlation_id: str
    ) -> StatusResponse:
        workflow_id = self.find_workflow_by_correlation_id(correlation_id)
        if workflow_id is None:
            raise KeyError(f"No workflow found for correlation_id: {correlation_id}")
        return await self.get_status(workflow_id)
