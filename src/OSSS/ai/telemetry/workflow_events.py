from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from OSSS.ai.events import emit_workflow_started, emit_workflow_completed


def _fire_and_forget(maybe_awaitable: Any) -> None:
    """
    Accept both sync and async emitters.
    If it's awaitable, schedule it. Never raises.
    """
    try:
        if asyncio.iscoroutine(maybe_awaitable):
            asyncio.create_task(maybe_awaitable)
    except Exception:
        pass


class WorkflowEvents:
    def __init__(self, *, api_version: str) -> None:
        self._api_version = api_version

    def started(self, *, ident: Any, request: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        _fire_and_forget(
            emit_workflow_started(
                workflow_id=ident.workflow_run_id,
                query=request.query,
                agents=list(getattr(request, "agents", None) or []),
                execution_config=request.execution_config or {},
                correlation_id=ident.correlation_id,
                metadata={"api_version": self._api_version, **(metadata or {})},
            )
        )

    def completed(
        self,
        *,
        ident: Any,
        response: Any,
        status: str,
        error_message: Optional[str],
    ) -> None:
        _fire_and_forget(
            emit_workflow_completed(
                workflow_id=ident.workflow_run_id,
                status=status,
                execution_time_seconds=response.execution_time_seconds,
                agent_outputs=(response.agent_outputs if status == "completed" else {}),
                error_message=(error_message if status != "completed" else None),
                correlation_id=response.correlation_id,
                metadata={"api_version": self._api_version, "agent_output_meta": response.agent_output_meta},
            )
        )
