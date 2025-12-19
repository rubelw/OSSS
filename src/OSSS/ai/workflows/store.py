# OSSS/ai/workflows/store.py
from __future__ import annotations
import time, asyncio
from typing import Any, Dict, Optional, Protocol, Iterable, List

from OSSS.ai.api.models import WorkflowRequest, WorkflowResponse, StatusResponse

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

    def start(self, workflow_id: str, *, request: WorkflowRequest, query_profile: Dict[str, Any]) -> None:
        self._active[workflow_id] = {
            "status": "running",
            "request": request,
            "start_time": time.time(),
            "workflow_id": workflow_id,
            "query_profile": query_profile,
        }

    def complete(self, workflow_id: str, *, status: str, response: Optional[WorkflowResponse] = None) -> None:
        if workflow_id in self._active:
            self._active[workflow_id]["status"] = status
            self._active[workflow_id]["end_time"] = time.time()
            if response is not None:
                self._active[workflow_id]["response"] = response

    def get_status(self, workflow_id: str) -> StatusResponse:
        if workflow_id not in self._active:
            raise KeyError(f"Workflow {workflow_id} not found")

        wf = self._active[workflow_id]
        status = wf["status"]
        progress = 100.0 if status in ("completed", "failed", "cancelled") else min(90.0, ((time.time() - wf["start_time"]) / 10.0) * 100.0)
        current_agent = None if status != "running" else "synthesis"
        est = None if status != "running" else max(1.0, 10.0 - (time.time() - wf["start_time"]))

        return StatusResponse(workflow_id=workflow_id, status=status, progress_percentage=progress, current_agent=current_agent, estimated_completion_seconds=est)

    async def cancel(self, workflow_id: str) -> bool:
        if workflow_id not in self._active:
            return False
        if self._active[workflow_id]["status"] in ("completed", "failed"):
            return False
        self._active[workflow_id]["status"] = "cancelled"
        self._active[workflow_id]["end_time"] = time.time()
        await asyncio.sleep(1)
        self._active.pop(workflow_id, None)
        return True

    def active_ids(self) -> Iterable[str]:
        return list(self._active.keys())

    def active_count(self) -> int:
        return len(self._active)
