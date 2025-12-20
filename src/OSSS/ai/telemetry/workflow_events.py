import asyncio
import logging
from typing import Any, Dict, Optional

from OSSS.ai.events import emit_workflow_started, emit_workflow_completed

# Set up logger for observability
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Change to INFO or ERROR as needed

def _fire_and_forget(maybe_awaitable: Any) -> None:
    """
    Accept both sync and async emitters.
    If it's awaitable, schedule it. Never raises.
    """
    try:
        if asyncio.iscoroutine(maybe_awaitable):
            logger.debug("Scheduling async emitter task")
            asyncio.create_task(maybe_awaitable)
        else:
            logger.debug("Firing sync emitter")
            maybe_awaitable()
    except Exception as e:
        logger.error(f"Failed to fire event: {e}")

class WorkflowEvents:
    def __init__(self, *, api_version: str) -> None:
        self._api_version = api_version
        logger.debug(f"Initialized WorkflowEvents with API version {api_version}")

    def started(self, *, ident: Any, request: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        logger.info(f"Workflow started: {ident.workflow_run_id} with query {request.query}")

        # Log metadata if available
        if metadata:
            logger.debug(f"Additional metadata: {metadata}")

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
        logger.info(f"Workflow completed: {ident.workflow_run_id} with status {status}")

        # Log error message if present
        if error_message:
            logger.error(f"Error in workflow {ident.workflow_run_id}: {error_message}")

        # Log metadata and agent outputs
        logger.debug(f"Execution time: {response.execution_time_seconds} seconds")
        if status == "completed":
            logger.debug(f"Agent outputs: {response.agent_outputs}")
        else:
            logger.debug(f"No agent outputs, status: {status}")

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
