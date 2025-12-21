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
import inspect


logger = get_logger(__name__)
router = APIRouter()


@router.post("/query", response_model=WorkflowResponse)
async def execute_query(request: WorkflowRequest) -> WorkflowResponse:
    try:
        logger.info(f"Executing query: {request.query[:100]}...")

        logger.info(f"get_orchestration_api is coroutine fn? {inspect.iscoroutinefunction(get_orchestration_api)}")

        orchestration_api = await get_orchestration_api()
        response: WorkflowResponse = await orchestration_api.execute_workflow(request)

        logger.info(f"Query executed successfully, correlation_id: {response.correlation_id}")
        return response

    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Workflow execution failed",
                "message": str(e),
                "type": type(e).__name__,
            },
        )


@router.get("/query/status/{correlation_id}", response_model=StatusResponse)
async def get_query_status(correlation_id: str) -> StatusResponse:
    try:
        logger.info(f"Getting status for correlation_id: {correlation_id}")

        orchestration_api = await get_orchestration_api()
        status_response: StatusResponse = await orchestration_api.get_status_by_correlation_id(correlation_id)

        logger.info(
            f"Status retrieved for correlation_id {correlation_id}: "
            f"workflow_id={status_response.workflow_id}, status={status_response.status}"
        )
        return status_response

    except KeyError as e:
        logger.warning(f"Correlation ID not found: {correlation_id}")
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Correlation ID not found",
                "message": str(e),
                "correlation_id": correlation_id,
            },
        )
    except Exception as e:
        logger.error(f"Failed to get status for correlation_id {correlation_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to retrieve workflow status",
                "message": str(e),
                "type": type(e).__name__,
            },
        )


@router.get("/query/history", response_model=WorkflowHistoryResponse)
async def get_query_history(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> WorkflowHistoryResponse:
    try:
        logger.info(f"Fetching workflow history: limit={limit}, offset={offset}")

        orchestration_api = await get_orchestration_api()
        raw_history: List[Dict[str, Any]] = await orchestration_api.get_workflow_history_from_database(
            limit=limit, offset=offset
        )

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
                logger.warning(f"Skipping invalid workflow data: {e}")
                continue

        total_workflows = offset + len(workflow_items)
        has_more = len(workflow_items) == limit

        return WorkflowHistoryResponse(
            workflows=workflow_items,
            total=total_workflows,
            limit=limit,
            offset=offset,
            has_more=has_more,
        )

    except Exception as e:
        logger.error(f"Failed to retrieve workflow history: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to retrieve workflow history",
                "message": str(e),
                "type": type(e).__name__,
            },
        )
