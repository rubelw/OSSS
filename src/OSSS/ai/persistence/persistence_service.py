# OSSS/ai/persistence/persistence_service.py
from __future__ import annotations
from typing import Any, Dict, Optional

from sqlalchemy.exc import IntegrityError

from OSSS.ai.database.connection import get_session_factory
from OSSS.ai.database.repositories.question_repository import QuestionRepository
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

class PersistenceService:
    def __init__(self) -> None:
        self._session_factory = get_session_factory()

    async def best_effort_save(self, *, request, response, workflow_id: str) -> None:
        try:
            async with self._session_factory() as session:
                repo = QuestionRepository(session)
                nodes_executed = list((response.agent_outputs or {}).keys())
                execution_metadata = {
                    "workflow_id": workflow_id,
                    "execution_time_seconds": response.execution_time_seconds,
                    "agent_outputs": response.agent_outputs,
                    "agents_requested": request.agents,
                    "export_md": bool(getattr(request, "export_md", False)),
                    "execution_config": request.execution_config or {},
                    "api_version": "1.0.0",
                    "status": response.status,
                    "error_message": response.error_message,
                    "orchestrator_type": "langgraph-real",
                }
                try:
                    await repo.create_question(
                        query=request.query,
                        correlation_id=response.correlation_id,
                        execution_id=workflow_id,
                        nodes_executed=nodes_executed,
                        execution_metadata=execution_metadata,
                    )
                except IntegrityError:
                    logger.info("Idempotent persistence (correlation_id already exists)", extra={"workflow_id": workflow_id})
        except Exception as e:
            logger.error("Persistence failed (best effort)", extra={"workflow_id": workflow_id, "error": str(e)})
