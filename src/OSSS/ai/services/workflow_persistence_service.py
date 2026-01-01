# OSSS/ai/services/workflow_persistence_service.py

from typing import Any, Dict, List, Optional
from collections.abc import Callable

from OSSS.ai.database.repositories.question_repository import QuestionRepository
from OSSS.ai.observability import get_logger
from OSSS.ai.database.session_factory import (
    DatabaseSessionFactory,
    get_database_session_factory,
)

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional
from collections.abc import Callable

from OSSS.ai.api.models import SkippedAgentOutput  # adjust path if needed


logger = get_logger(__name__)


class WorkflowPersistenceService:
    """
    Best-effort workflow persistence service.

    Uses the AI-layer DatabaseSessionFactory, which in turn delegates to the
    canonical DB engine + sessionmaker from OSSS.db.session via
    OSSS.ai.database.session_factory.
    """

    def __init__(
        self,
        session_factory_provider: Callable[[], DatabaseSessionFactory]
        = get_database_session_factory,
        api_version: str = "1.0.0",
    ):
        """
        session_factory_provider should return a DatabaseSessionFactory instance.
        By default we use the global one from OSSS.ai.database.session_factory,
        which is backed by OSSS.db.session.get_engine/get_sessionmaker.
        """
        self._session_factory_provider = session_factory_provider
        self._api_version = api_version


    # ------------------------------------------------------------------ #
    # JSON-safe helpers                                                  #
    # ------------------------------------------------------------------ #

    def _to_json_safe(self, value: Any) -> Any:
        """
        Recursively convert values to something json.dumps can handle.

        - Handles SkippedAgentOutput (and other dataclasses) explicitly.
        - Converts mappings and sequences recursively.
        - Falls back to str() for unknown custom objects.
        """
        # 1. SkippedAgentOutput (and similar typed objects)
        if isinstance(value, SkippedAgentOutput):
            return {
                "type": "skipped",
                "agent": getattr(value, "agent_name", None),
                "reason": getattr(value, "reason", None),
                "meta": self._to_json_safe(getattr(value, "meta", None))
                if hasattr(value, "meta")
                else None,
            }

        # If you have other concrete output types, handle them here:
        # from OSSS.ai.orchestration.state_schemas import CompletedAgentOutput
        # if isinstance(value, CompletedAgentOutput):
        #     return {
        #         "type": "completed",
        #         "agent": value.agent_name,
        #         "result": self._to_json_safe(value.result),
        #         "processing_time_ms": getattr(value, "processing_time_ms", None),
        #     }

        # 2. Dataclasses in general
        if is_dataclass(value):
            return {k: self._to_json_safe(v) for k, v in asdict(value).items()}

        # 3. Mappings
        if isinstance(value, dict):
            return {k: self._to_json_safe(v) for k, v in value.items()}

        # 4. Sequences
        if isinstance(value, (list, tuple, set)):
            return [self._to_json_safe(v) for v in value]

        # 5. Pydantic-style objects (Pydantic v1/v2)
        if hasattr(value, "model_dump") and callable(getattr(value, "model_dump")):
            return self._to_json_safe(value.model_dump())
        if hasattr(value, "dict") and callable(getattr(value, "dict")):
            return self._to_json_safe(value.dict())

        # 6. Primitive / already-jsonable types (str, int, float, bool, None)
        # just pass through
        return value

    async def _get_initialized_factory(self) -> Optional[DatabaseSessionFactory]:
        """
        Internal helper to get an initialized DatabaseSessionFactory.

        Returns None if:
        - provider returns None
        - provider returns an unexpected type (e.g. a bare function/class)
        - initialization fails

        This keeps persistence best-effort and avoids crashing the main request.
        """
        try:
            factory = self._session_factory_provider()
        except Exception as e:
            logger.warning(
                "Session factory provider raised; skipping workflow persistence",
                extra={"error": str(e)},
                exc_info=True,
            )
            return None

        if factory is None:
            logger.debug(
                "Session factory provider returned None; skipping persistence"
            )
            return None

        # Defensive: make sure we didn't accidentally get a function or class
        if not isinstance(factory, DatabaseSessionFactory) and not (
            hasattr(factory, "is_initialized") and hasattr(factory, "get_session")
        ):
            logger.warning(
                "Session factory provider returned unexpected type; "
                "skipping workflow persistence",
                extra={"returned_type": type(factory).__name__},
            )
            return None

        # Initialize if needed
        is_initialized = getattr(factory, "is_initialized", False)
        if not is_initialized:
            try:
                await factory.initialize()
            except Exception as e:
                logger.warning(
                    "Failed to initialize DatabaseSessionFactory; "
                    "skipping workflow persistence",
                    extra={"error": str(e)},
                    exc_info=True,
                )
                return None

        return factory  # type: ignore[return-value]

    async def persist_success(
            self,
            request: Any,
            response: Any,
            workflow_id: str,
            original_execution_config: Dict[str, Any],
    ) -> None:
        """
        Persist a successful workflow execution.

        This is intentionally best-effort: any DB errors are logged
        but do NOT affect the caller's HTTP response.
        """
        factory = await self._get_initialized_factory()
        if factory is None:
            return

        planned_agents = self._extract_planned_agents(
            request=request,
            response=response,
            original_execution_config=original_execution_config,
        )

        raw_agent_outputs: Dict[str, Any] = getattr(response, "agent_outputs", {}) or {}

        execution_metadata: Dict[str, Any] = {
            "status": "success",
            "workflow_id": workflow_id,
            "execution_time_seconds": getattr(
                response, "execution_time_seconds", None
            ),
            # IMPORTANT: make JSON-safe
            "agent_outputs": self._to_json_safe(raw_agent_outputs),
            "agents_requested": planned_agents,
            "export_md": bool(getattr(request, "export_md", False)),
            "execution_config": self._to_json_safe(original_execution_config),
            "api_version": self._api_version,
            "orchestrator_type": "langgraph-real",
        }

        # Best-effort extraction of nodes actually executed
        nodes_executed: List[str] = list(raw_agent_outputs.keys())

        # 🔑 Option A: use the *response* correlation_id as the authoritative one
        correlation_id = (
                getattr(response, "correlation_id", None)
                or getattr(request, "correlation_id", None)
        )

        try:
            async with factory.get_session() as session:
                question_repo = QuestionRepository(session)
                await question_repo.create_question(
                    query=getattr(request, "query", None),
                    correlation_id=correlation_id,
                    execution_id=workflow_id,
                    nodes_executed=nodes_executed,
                    execution_metadata=execution_metadata,
                )
            logger.info(
                "Workflow persisted to database",
                extra={"workflow_id": workflow_id, "correlation_id": correlation_id},
            )
        except Exception as e:
            logger.warning(
                "Workflow persistence failed; continuing without DB persistence",
                extra={
                    "workflow_id": workflow_id,
                    "correlation_id": correlation_id,
                    "error": str(e),
                },
                exc_info=True,
            )

    async def persist_failure(
            self,
            request: Any,
            response: Optional[Any],
            workflow_id: str,
            error_message: str,
            original_execution_config: Dict[str, Any],
    ) -> None:
        """
        Persist a failed workflow execution.

        Mirrors persist_success but tags status + error_message
        in execution_metadata. Safe to call with response=None.
        """
        factory = await self._get_initialized_factory()
        if factory is None:
            return

        planned_agents: List[str] = []
        agent_outputs: Dict[str, Any] = {}
        execution_time_seconds: Optional[float] = None
        nodes_executed: List[str] = []

        if response is not None:
            planned_agents = self._extract_planned_agents(
                request=request,
                response=response,
                original_execution_config=original_execution_config,
            )
            agent_outputs = getattr(response, "agent_outputs", {}) or {}
            execution_time_seconds = getattr(response, "execution_time_seconds", None)
            nodes_executed = list(agent_outputs.keys())

        execution_metadata: Dict[str, Any] = {
            "status": "error",
            "workflow_id": workflow_id,
            "execution_time_seconds": execution_time_seconds,
            "agent_outputs": self._to_json_safe(agent_outputs),
            "agents_requested": planned_agents,
            "export_md": bool(getattr(request, "export_md", False)),
            "execution_config": self._to_json_safe(original_execution_config),
            "api_version": self._api_version,
            "orchestrator_type": "langgraph-real",
            "error_message": error_message,
        }

        # 🔑 Option A: again, prefer response.correlation_id if present
        correlation_id = None
        if response is not None:
            correlation_id = getattr(response, "correlation_id", None)
        if correlation_id is None:
            correlation_id = getattr(request, "correlation_id", None)

        try:
            async with factory.get_session() as session:
                question_repo = QuestionRepository(session)
                await question_repo.create_question(
                    query=getattr(request, "query", None),
                    correlation_id=correlation_id,
                    execution_id=workflow_id,
                    nodes_executed=nodes_executed,
                    execution_metadata=execution_metadata,
                )
            logger.info(
                "Failed workflow persisted to database",
                extra={"workflow_id": workflow_id, "correlation_id": correlation_id},
            )
        except Exception as e:
            logger.warning(
                "Failed-workflow persistence errored; continuing without DB persistence",
                extra={
                    "workflow_id": workflow_id,
                    "correlation_id": correlation_id,
                    "original_error": error_message,
                    "persistence_error": str(e),
                },
                exc_info=True,
            )

    # --------------------------------------------------------------------- #
    # Internal helpers                                                      #
    # --------------------------------------------------------------------- #

    def _extract_planned_agents(
        self,
        request: Any,
        response: Any,
        original_execution_config: Dict[str, Any],
    ) -> List[str]:
        """
        Derive the authoritative list of planned/requested agents.

        Priority:
        1. response.execution_state["planned_agents"]
        2. response.execution_state["agents_requested"]
        3. response.agents_requested / response.agents (if present)
        4. original_execution_config["agents_to_run"] / ["planned_agents"]
        5. request.agents (last resort)

        Order is preserved; duplicates are removed.
        """
        candidates: List[str] = []

        # 1/2. From execution_state (LangGraph-native)
        exec_state = getattr(response, "execution_state", None)
        if isinstance(exec_state, dict):
            planned = exec_state.get("planned_agents") or exec_state.get(
                "agents_requested"
            )
            if isinstance(planned, list):
                candidates.extend(str(a) for a in planned)

        # 3. From response attributes (if any)
        if not candidates:
            resp_agents = getattr(response, "agents_requested", None) or getattr(
                response, "agents", None
            )
            if isinstance(resp_agents, list):
                candidates.extend(str(a) for a in resp_agents)

        # 4. From original_execution_config
        if not candidates and isinstance(original_execution_config, dict):
            cfg_agents = original_execution_config.get("agents_to_run") or (
                original_execution_config.get("planned_agents")
            )
            if isinstance(cfg_agents, list):
                candidates.extend(str(a) for a in cfg_agents)

        # 5. From request (last-resort)
        if not candidates:
            req_agents = getattr(request, "agents", None)
            if isinstance(req_agents, list):
                candidates.extend(str(a) for a in req_agents)

        # Deduplicate preserving order
        seen = set()
        deduped: List[str] = []
        for a in candidates:
            if a not in seen:
                seen.add(a)
                deduped.append(a)

        return deduped
