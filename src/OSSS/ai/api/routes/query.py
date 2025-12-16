"""
Query execution endpoints for the OSSS API.

This module defines the FastAPI routes responsible for:
- Executing multi-agent workflows via the orchestration layer
- Retrieving execution status by correlation ID
- Fetching paginated workflow execution history

The endpoints here act strictly as a thin API layer:
- No business logic lives here
- All orchestration and persistence concerns are delegated
  to the orchestration API obtained via the factory pattern
"""

# ---------------------------------------------------------------------------
# Standard library / typing imports
# ---------------------------------------------------------------------------

from typing import Dict, Any, List

# ---------------------------------------------------------------------------
# FastAPI imports
# ---------------------------------------------------------------------------

from fastapi import APIRouter, HTTPException, Query

# ---------------------------------------------------------------------------
# API request / response models
# These are Pydantic models defining the public API contract
# ---------------------------------------------------------------------------

from OSSS.ai.api.models import (
    WorkflowRequest,          # Incoming request payload for workflow execution
    WorkflowResponse,         # Response returned after execution
    WorkflowHistoryResponse,  # Paginated response for workflow history
    WorkflowHistoryItem,      # Individual workflow history record
    StatusResponse,           # Workflow status response model
)

# ---------------------------------------------------------------------------
# Orchestration factory
# Centralized access point for the orchestration layer
# ---------------------------------------------------------------------------

from OSSS.ai.api.factory import get_orchestration_api

# ---------------------------------------------------------------------------
# Observability / logging
# ---------------------------------------------------------------------------

from OSSS.ai.observability import get_logger

# Create a module-level logger scoped to this file
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# FastAPI router instance
# All endpoints in this module will be mounted under a parent router
# ---------------------------------------------------------------------------

router = APIRouter()


# ===========================================================================
# POST /query
# ===========================================================================
@router.post("/query", response_model=WorkflowResponse)
async def execute_query(request: WorkflowRequest) -> WorkflowResponse:
    """
    Execute a multi-agent workflow using the existing orchestration system.

    This endpoint:
    - Accepts a user query and optional workflow configuration
    - Ensures the orchestration layer is initialized
    - Delegates execution to the orchestration API
    - Returns a typed WorkflowResponse with metadata and results

    Args:
        request:
            WorkflowRequest containing:
            - query text
            - optional agent / workflow configuration

    Returns:
        WorkflowResponse:
            - correlation_id for tracking
            - workflow_id
            - execution status
            - results and metadata

    Raises:
        HTTPException (500):
            Raised if any unhandled exception occurs during execution
    """
    try:
        # Log the query execution request
        # Only log the first 100 characters to avoid excessive log volume
        logger.info(f"Executing query: {request.query[:100]}...")

        # Obtain the orchestration API via factory
        # This allows lazy initialization and swapping implementations
        orchestration_api = get_orchestration_api()

        # Ensure orchestration API is initialized
        # The `_initialized` attribute is a soft contract used internally
        if not getattr(orchestration_api, "_initialized", False):
            await orchestration_api.initialize()

        # Execute the workflow asynchronously
        response: WorkflowResponse = await orchestration_api.execute_workflow(request)

        # Log successful execution with correlation ID for traceability
        logger.info(
            f"Query executed successfully, correlation_id: {response.correlation_id}"
        )

        return response

    except Exception as e:
        # Log full exception details for debugging and observability
        logger.error(f"Query execution failed: {e}")

        # Convert internal error into a standardized HTTP 500 response
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Workflow execution failed",
                "message": str(e),
                "type": type(e).__name__,
            },
        )


# ===========================================================================
# GET /query/status/{correlation_id}
# ===========================================================================
@router.get("/query/status/{correlation_id}", response_model=StatusResponse)
async def get_query_status(correlation_id: str) -> StatusResponse:
    """
    Retrieve the current status of a previously submitted workflow.

    This endpoint allows clients to:
    - Poll for workflow progress
    - Retrieve execution status using a correlation ID
    - Avoid direct exposure of internal workflow IDs

    Args:
        correlation_id:
            External identifier returned at workflow submission time

    Returns:
        StatusResponse:
            - workflow_id
            - current status (running, completed, failed, etc.)
            - progress metadata

    Raises:
        HTTPException (404):
            If the correlation ID does not exist

        HTTPException (500):
            If the orchestration API fails unexpectedly
    """
    try:
        logger.info(f"Getting status for correlation_id: {correlation_id}")

        # Obtain orchestration API instance
        orchestration_api = get_orchestration_api()

        # Retrieve status by correlation ID
        # Internally maps correlation_id -> workflow_id
        status_response: StatusResponse = (
            await orchestration_api.get_status_by_correlation_id(correlation_id)
        )

        # Log resolved workflow details
        logger.info(
            f"Status retrieved for correlation_id {correlation_id}: "
            f"workflow_id={status_response.workflow_id}, "
            f"status={status_response.status}"
        )

        return status_response

    except KeyError as e:
        # Correlation ID does not exist or mapping not found
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
        # Catch-all for unexpected failures
        logger.error(f"Failed to get status for correlation_id {correlation_id}: {e}")

        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to retrieve workflow status",
                "message": str(e),
                "type": type(e).__name__,
            },
        )


# ===========================================================================
# GET /query/history
# ===========================================================================
@router.get("/query/history", response_model=WorkflowHistoryResponse)
async def get_query_history(
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results to return",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of results to skip for pagination",
    ),
) -> WorkflowHistoryResponse:
    """
    Retrieve paginated workflow execution history.

    This endpoint:
    - Fetches workflow records from persistent storage
    - Supports limit/offset pagination
    - Converts raw database records into typed API models

    History records typically include:
    - workflow ID
    - execution status
    - truncated query text
    - start time
    - execution duration

    Args:
        limit:
            Maximum number of workflows to return (1–100)

        offset:
            Number of workflows to skip (used for pagination)

    Returns:
        WorkflowHistoryResponse:
            - list of WorkflowHistoryItem entries
            - pagination metadata (limit, offset, total, has_more)

    Raises:
        HTTPException (500):
            If history retrieval fails
    """
    try:
        logger.info(f"Fetching workflow history: limit={limit}, offset={offset}")

        # Obtain orchestration API instance
        orchestration_api = get_orchestration_api()

        # Retrieve raw workflow history from the database
        # Pagination is already applied at the data access layer
        raw_history: List[Dict[str, Any]] = (
            await orchestration_api.get_workflow_history_from_database(
                limit=limit,
                offset=offset,
            )
        )

        logger.debug(f"Raw history retrieved: {len(raw_history)} workflows")

        # Convert raw database rows into typed Pydantic models
        workflow_items: List[WorkflowHistoryItem] = []

        for workflow_data in raw_history:
            try:
                workflow_item = WorkflowHistoryItem(
                    workflow_id=workflow_data["workflow_id"],
                    status=workflow_data["status"],
                    query=workflow_data["query"],  # Already truncated upstream
                    start_time=workflow_data["start_time"],
                    execution_time_seconds=workflow_data["execution_time"],
                )
                workflow_items.append(workflow_item)

            except (KeyError, ValueError) as e:
                # Skip malformed or incomplete records
                logger.warning(f"Skipping invalid workflow data: {e}")
                continue

        # Estimate total count and pagination state
        # NOTE:
        # - This is a lower-bound estimate
        # - A future enhancement should include a COUNT(*) query
        total_workflows = offset + len(workflow_items)

        # If we returned a full page, assume more records may exist
        has_more = len(workflow_items) == limit

        response = WorkflowHistoryResponse(
            workflows=workflow_items,
            total=total_workflows,
            limit=limit,
            offset=offset,
            has_more=has_more,
        )

        logger.info(
            f"Workflow history retrieved: {len(workflow_items)} items, "
            f"total={total_workflows}, has_more={has_more}"
        )

        return response

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
