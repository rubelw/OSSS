# OSSS/ai/api/orchestration_api.py
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

    async def initialize(self) -> None:
        if self._initialized:
            return
        # Wire dependencies in one place.
        self._service = OrchestrationService(store=self._store)
        await self._service.initialize()
        self._initialized = True

    async def shutdown(self) -> None:
        if not self._initialized:
            return
        assert self._service is not None
        await self._service.shutdown()
        self._initialized = False

    @property
    def api_name(self) -> str:
        return "LangGraph Orchestration API"

    @property
    def api_version(self) -> str:
        return "1.0.0"

    @ensure_initialized
    async def execute_workflow(self, request: WorkflowRequest) -> WorkflowResponse:
        assert self._service is not None
        return await self._service.execute(request)

    @ensure_initialized
    async def get_status(self, workflow_id: str) -> StatusResponse:
        return self._store.get_status(workflow_id)

    @ensure_initialized
    async def cancel_workflow(self, workflow_id: str) -> bool:
        return await self._store.cancel(workflow_id)

    async def health_check(self) -> APIHealthStatus:
        checks = {
            "initialized": self._initialized,
            "active_workflows": self._store.active_count(),
        }
        if not self._initialized:
            return APIHealthStatus(status=HealthStatus.UNHEALTHY, details="API not initialized", checks=checks)
        return APIHealthStatus(status=HealthStatus.HEALTHY, details="OK", checks=checks)

    async def get_metrics(self) -> Dict[str, Any]:
        # Keep stable shape; service can enrich later
        return {
            "active_workflows": self._store.active_count(),
            "api_initialized": self._initialized,
            "api_version": self.api_version,
        }
