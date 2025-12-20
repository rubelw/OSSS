from __future__ import annotations
import time, asyncio
from typing import Any, Dict, Optional, Protocol, Iterable, List

from OSSS.ai.api.models import WorkflowRequest, WorkflowResponse, StatusResponse
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

class WorkflowStore(Protocol):
    def start(self, workflow_id: str, *, request: WorkflowRequest, query_profile: Dict[str, Any]) -> None: ...
    def complete(self, workflow_id: str, *, status: str, response: Optional[WorkflowResponse] = None) -> None: ...
    def get_status(self, workflow_id: str) -> StatusResponse: ...
    async def cancel(self, workflow_id: str) -> bool: ...
    def active_ids(self) -> Iterable[str]: ...
    def active_count(self) -> int: ...

class InMemoryWorkflowStore:
    def __init__(self) -> None:
        self._active: Dict[str, Dict[str, Any]] = {}
        logger.debug("InMemoryWorkflowStore initialized")

    def start(self, workflow_id: str, *, request: WorkflowRequest, query_profile: Dict[str, Any]) -> None:
        logger.debug(f"Starting workflow {workflow_id} with request {request} and query profile {query_profile}")
        self._active[workflow_id] = {
            "status": "running",
            "request": request,
            "start_time": time.time(),
            "workflow_id": workflow_id,
            "query_profile": query_profile,
        }
        logger.info(f"Workflow {workflow_id} started")

    def complete(self, workflow_id: str, *, status: str, response: Optional[WorkflowResponse] = None) -> None:
        logger.debug(f"Completing workflow {workflow_id} with status {status} and response {response}")
        if workflow_id in self._active:
            self._active[workflow_id]["status"] = status
            self._active[workflow_id]["end_time"] = time.time()
            if response is not None:
                self._active[workflow_id]["response"] = response
            logger.info(f"Workflow {workflow_id} completed with status {status}")
        else:
            logger.warning(f"Workflow {workflow_id} not found for completion")

    def get_status(self, workflow_id: str) -> StatusResponse:
        logger.debug(f"Getting status for workflow {workflow_id}")
        if workflow_id not in self._active:
            logger.error(f"Workflow {workflow_id} not found")
            raise KeyError(f"Workflow {workflow_id} not found")

        wf = self._active[workflow_id]
        status = wf["status"]
        progress = 100.0 if status in ("completed", "failed", "cancelled") else min(90.0, ((time.time() - wf["start_time"]) / 10.0) * 100.0)
        current_agent = None if status != "running" else "synthesis"
        est = None if status != "running" else max(1.0, 10.0 - (time.time() - wf["start_time"]))

        logger.debug(f"Workflow {workflow_id} status: {status}, progress: {progress}%, current_agent: {current_agent}, estimated_completion_seconds: {est}")
        return StatusResponse(workflow_id=workflow_id, status=status, progress_percentage=progress, current_agent=current_agent, estimated_completion_seconds=est)

    async def cancel(self, workflow_id: str) -> bool:
        logger.debug(f"Attempting to cancel workflow {workflow_id}")
        if workflow_id not in self._active:
            logger.warning(f"Workflow {workflow_id} not found for cancellation")
            return False
        if self._active[workflow_id]["status"] in ("completed", "failed"):
            logger.warning(f"Workflow {workflow_id} cannot be cancelled as it is already {self._active[workflow_id]['status']}")
            return False
        self._active[workflow_id]["status"] = "cancelled"
        self._active[workflow_id]["end_time"] = time.time()
        await asyncio.sleep(1)
        self._active.pop(workflow_id, None)
        logger.info(f"Workflow {workflow_id} cancelled")
        return True

    def active_ids(self) -> Iterable[str]:
        active_ids = list(self._active.keys())
        logger.debug(f"Active workflow IDs: {active_ids}")
        return active_ids

    def active_count(self) -> int:
        count = len(self._active)
        logger.debug(f"Number of active workflows: {count}")
        return count
