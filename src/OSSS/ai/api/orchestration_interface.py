from __future__ import annotations

from typing import Any, Dict, List, Protocol

from OSSS.ai.api.models import WorkflowRequest, WorkflowResponse, StatusResponse


class OrchestrationAPI(Protocol):
    async def initialize(self) -> None: ...

    async def execute_workflow(self, request: WorkflowRequest) -> WorkflowResponse: ...

    async def get_status_by_correlation_id(self, correlation_id: str) -> StatusResponse: ...

    async def get_workflow_history_from_database(
        self, limit: int = 10, offset: int = 0
    ) -> List[Dict[str, Any]]: ...
