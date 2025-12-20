from __future__ import annotations
from typing import Dict, Any, Optional, List

from OSSS.ai.api.external import OrchestrationAPI
from OSSS.ai.api.models import WorkflowRequest, WorkflowResponse, StatusResponse
from OSSS.ai.api.base import APIHealthStatus
from OSSS.ai.api.decorators import ensure_initialized

from OSSS.ai.app.orchestration_service import OrchestrationService
from OSSS.ai.workflows.store import WorkflowStore, InMemoryWorkflowStore
from OSSS.ai.diagnostics.health import HealthStatus
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)


class LangGraphOrchestrationAPI(OrchestrationAPI):
    def __init__(self) -> None:
        self._initialized = False
        self._service: Optional[OrchestrationService] = None
        self._store: WorkflowStore = InMemoryWorkflowStore()
        logger.debug("LangGraphOrchestrationAPI instance created")

    async def initialize(self) -> None:
        if self._initialized:
            logger.debug("LangGraphOrchestrationAPI is already initialized")
            return

        logger.info("Initializing LangGraphOrchestrationAPI...")
        # Wire dependencies in one place.
        self._service = OrchestrationService(store=self._store)
        await self._service.initialize()
        self._initialized = True
        logger.info("LangGraphOrchestrationAPI initialized successfully")

    async def shutdown(self) -> None:
        if not self._initialized:
            logger.debug("LangGraphOrchestrationAPI is not initialized, skipping shutdown")
            return

        logger.info("Shutting down LangGraphOrchestrationAPI...")
        assert self._service is not None
        await self._service.shutdown()
        self._initialized = False
        logger.info("LangGraphOrchestrationAPI shutdown complete")

    @property
    def api_name(self) -> str:
        return "LangGraph Orchestration API"

    @property
    def api_version(self) -> str:
        return "1.0.0"

    @ensure_initialized
    async def execute_workflow(self, request: WorkflowRequest) -> WorkflowResponse:
        logger.debug(f"Executing workflow with id: {request.workflow_id}")
        assert self._service is not None
        try:
            response = await self._service.execute(request)
            logger.info(f"Workflow execution complete for id: {request.workflow_id}")
            return response
        except Exception as e:
            logger.error(f"Error executing workflow {request.workflow_id}: {str(e)}")
            raise

    @ensure_initialized
    async def get_status(self, workflow_id: str) -> StatusResponse:
        logger.debug(f"Fetching status for workflow id: {workflow_id}")
        status = self._store.get_status(workflow_id)
        logger.info(f"Status for workflow {workflow_id}: {status.status}")
        return status

    @ensure_initialized
    async def cancel_workflow(self, workflow_id: str) -> bool:
        logger.debug(f"Cancelling workflow with id: {workflow_id}")
        result = await self._store.cancel(workflow_id)
        if result:
            logger.info(f"Workflow {workflow_id} cancelled successfully")
        else:
            logger.warning(f"Failed to cancel workflow {workflow_id}")
        return result

    async def health_check(self) -> APIHealthStatus:
        logger.debug("Performing health check for LangGraphOrchestrationAPI")
        checks = {
            "initialized": self._initialized,
            "active_workflows": self._store.active_count(),
        }
        if not self._initialized:
            logger.warning("LangGraphOrchestrationAPI is not initialized, returning unhealthy status")
            return APIHealthStatus(status=HealthStatus.UNHEALTHY, details="API not initialized", checks=checks)

        logger.info("LangGraphOrchestrationAPI health check passed")
        return APIHealthStatus(status=HealthStatus.HEALTHY, details="OK", checks=checks)

    async def get_metrics(self) -> Dict[str, Any]:
        logger.debug("Retrieving metrics for LangGraphOrchestrationAPI")
        metrics = {
            "active_workflows": self._store.active_count(),
            "api_initialized": self._initialized,
            "api_version": self.api_version,
        }
        logger.info(f"LangGraphOrchestrationAPI metrics: {metrics}")
        return metrics
