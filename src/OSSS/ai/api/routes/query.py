"""
Query execution endpoints for the OSSS API.
...
"""

from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException, Query

from OSSS.ai.api.models import (
    WorkflowRequest,
    WorkflowResponse,
    WorkflowHistoryResponse,
    WorkflowHistoryItem,
    StatusResponse,
)

from OSSS.ai.api.factory import get_orchestration_api
from OSSS.ai.observability import get_logger
from OSSS.ai.api.models import WorkflowHistoryResponse, WorkflowHistoryItem

# ✅ use shared sanitizer
from OSSS.ai.utils import _sanitize_for_json  # adjust import if your utils live elsewhere

logger = get_logger(__name__)
router = APIRouter()


@router.post("/query", response_model=WorkflowResponse)
async def execute_query(request: WorkflowRequest) -> WorkflowResponse:
    try:
        logger.info("Executing query", query=request.query[:100])

        orchestration_api = get_orchestration_api()
        if not getattr(orchestration_api, "_initialized", False):
            await orchestration_api.initialize()

        response: WorkflowResponse = await orchestration_api.execute_workflow(request)

        # ✅ sanitize the whole response to avoid Pydantic circular refs / ORM objects
        sanitized_payload = _sanitize_for_json(response.model_dump(mode="python"))
        sanitized_response = WorkflowResponse.model_validate(sanitized_payload)

        logger.info(
            "Query executed successfully",
            correlation_id=sanitized_response.correlation_id,
        )
        return sanitized_response

    except Exception as e:
        # ✅ keep stack trace + structured fields
        logger.exception("Query execution failed", error_type=type(e).__name__)

        # ✅ sanitize detail too (FastAPI will serialize this)
        detail = _sanitize_for_json(
            {
                "error": "Workflow execution failed",
                "message": str(e),
                "type": type(e).__name__,
            }
        )
        raise HTTPException(status_code=500, detail=detail)


@router.get("/query/status/{correlation_id}", response_model=StatusResponse)
async def get_query_status(correlation_id: str) -> StatusResponse:
    try:
        logger.info("Getting status", correlation_id=correlation_id)

        orchestration_api = get_orchestration_api()
        status_response: StatusResponse = await orchestration_api.get_status_by_correlation_id(
            correlation_id
        )

        # Optional: sanitize if your status model ever includes non-JSON types
        sanitized_payload = _sanitize_for_json(status_response.model_dump(mode="python"))
        sanitized_status = StatusResponse.model_validate(sanitized_payload)

        logger.info(
            "Status retrieved",
            correlation_id=correlation_id,
            workflow_id=sanitized_status.workflow_id,
            status=sanitized_status.status,
        )
        return sanitized_status

    except KeyError as e:
        logger.warning("Correlation ID not found", correlation_id=correlation_id)
        raise HTTPException(
            status_code=404,
            detail=_sanitize_for_json(
                {
                    "error": "Correlation ID not found",
                    "message": str(e),
                    "correlation_id": correlation_id,
                }
            ),
        )

    except Exception as e:
        logger.exception("Failed to get status", correlation_id=correlation_id)
        raise HTTPException(
            status_code=500,
            detail=_sanitize_for_json(
                {
                    "error": "Failed to retrieve workflow status",
                    "message": str(e),
                    "type": type(e).__name__,
                }
            ),
        )


@router.get("/query/history", response_model=WorkflowHistoryResponse)
async def get_query_history(
    limit: int = Query(default=10, ge=1, le=100, description="Maximum number of results to return"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip for pagination"),
) -> WorkflowHistoryResponse:
    try:
        logger.info("Fetching workflow history", limit=limit, offset=offset)

        orchestration_api = get_orchestration_api()
        raw_history: List[Dict[str, Any]] = await orchestration_api.get_workflow_history_from_database(
            limit=limit,
            offset=offset,
        )

        logger.debug("Raw history retrieved", workflow_count=len(raw_history))

        workflow_items: List[WorkflowHistoryItem] = []
        for workflow_data in raw_history:
            try:
                workflow_items.append(
                    WorkflowHistoryItem(
                        workflow_id=workflow_data["workflow_id"],
                        status=workflow_data["status"],
                        query=workflow_data["query"],
                        start_time=workflow_data["start_time"],
                        execution_time_seconds=workflow_data["execution_time"],
                    )
                )
            except (KeyError, ValueError) as e:
                logger.warning("Skipping invalid workflow data", error=str(e))
                continue

        total_workflows = offset + len(workflow_items)
        has_more = len(workflow_items) == limit

        response = WorkflowHistoryResponse(
            workflows=workflow_items,
            total=total_workflows,
            limit=limit,
            offset=offset,
            has_more=has_more,
        )

        # Optional: sanitize history too (usually not needed if DB rows are primitives)
        sanitized_payload = _sanitize_for_json(response.model_dump(mode="python"))
        sanitized_response = WorkflowHistoryResponse.model_validate(sanitized_payload)

        logger.info(
            "Workflow history retrieved",
            items=len(workflow_items),
            total=total_workflows,
            has_more=has_more,
        )
        return sanitized_response

    except Exception as e:
        logger.exception("Failed to retrieve workflow history")
        raise HTTPException(
            status_code=500,
            detail=_sanitize_for_json(
                {
                    "error": "Failed to retrieve workflow history",
                    "message": str(e),
                    "type": type(e).__name__,
                }
            ),
        )
