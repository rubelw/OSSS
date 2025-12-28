# OSSS/ai/services/workflow_persistence_service.py

from typing import Any, Dict, List, Optional
from OSSS.ai.database.connection import get_session_factory
from OSSS.ai.database.repositories.question_repository import QuestionRepository
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

class WorkflowPersistenceService:
    def __init__(self, session_factory_provider=get_session_factory, api_version: str = "1.0.0"):
        self._session_factory_provider = session_factory_provider
        self._api_version = api_version

    async def persist_success(
        self,
        request,
        response,
        workflow_id: str,
        original_execution_config: Dict[str, Any],
    ) -> None:
        sf = self._session_factory_provider()
        if sf is None:
            logger.debug("DB persistence disabled; skipping workflow persistence")
            return

        planned_agents = self._extract_planned_agents(request, response, original_execution_config)
        execution_metadata = {
            "workflow_id": workflow_id,
            "execution_time_seconds": response.execution_time_seconds,
            "agent_outputs": response.agent_outputs,
            "agents_requested": planned_agents,
            "export_md": bool(getattr(request, "export_md", False)),
            "execution_config": original_execution_config,
            "api_version": self._api_version,
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

    async def persist_failure(
        self,
        request,
        response,
        workflow_id: str,
        error_message: str,
        original_execution_config: Dict[str, Any],
    ) -> None:
        # analogous to persist_success, but include status/error_message
        ...
