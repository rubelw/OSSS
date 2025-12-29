from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException, Query, Request

from OSSS.ai.api.models import (
    WorkflowRequest,
    WorkflowResponse,
    WorkflowHistoryResponse,
    WorkflowHistoryItem,
    StatusResponse,
)

from OSSS.ai.api.factory import get_orchestration_api
from OSSS.ai.observability import get_logger


logger = get_logger(__name__)
router = APIRouter()


@router.post("/query", response_model=WorkflowResponse)
async def execute_query(http_request: Request, request: WorkflowRequest) -> WorkflowResponse:
    try:
        # ---------------------------------------------------------
        # Log raw body + parsed agents to debug "forced agents"
        # ---------------------------------------------------------
        raw = await http_request.body()
        raw_text = raw.decode("utf-8", errors="replace")

        logger.info(
            "Received /query request",
            extra={
                "raw_body": raw_text,
                "agents": request.agents,
                "query_length": len(request.query or ""),
                "correlation_id": getattr(request, "correlation_id", None),
                # 👇 NEW: log conversation_id if present
                "conversation_id": getattr(request, "conversation_id", None),
            },
        )

        # ---------------------------------------------------------
        # ✅ OPTION A: Normalize caller intent at API boundary
        #
        # Goals:
        # - agents=[]  -> treat as NOT PROVIDED
        # - fastpath (graph_pattern=refiner_final) must not be overridden
        # ---------------------------------------------------------
        exec_cfg = request.execution_config if isinstance(request.execution_config, dict) else {}

        fastpath = exec_cfg.get("graph_pattern") == "standard"

        # Treat empty list as "unset"
        if request.agents is not None and len(request.agents) == 0:
            request.agents = None

        # Fastpath must not be overridden by caller or execution_config
        if fastpath:
            request.agents = None
            if isinstance(request.execution_config, dict):
                request.execution_config.pop("agents", None)

            logger.info(
                "[api] fastpath enforced at route level",
                extra={
                    "graph_pattern": "standard",
                    "agents": None,
                    # keep correlation / conversation context in the logs
                    "correlation_id": getattr(request, "correlation_id", None),
                    "conversation_id": getattr(request, "conversation_id", None),
                },
            )

        # ---------------------------------------------------------
        # Execute workflow
        # ---------------------------------------------------------
        orchestration_api = await get_orchestration_api()
        response: WorkflowResponse = await orchestration_api.execute_workflow(request)

        if not response:
            logger.error("Response is None. Unable to proceed.")
            raise HTTPException(status_code=500, detail="Workflow execution failed. No response.")

        # Ensure the workflow_id is available
        if not hasattr(response, "workflow_id") or response.workflow_id is None:
            logger.error("Response does not contain a valid workflow_id.")
            raise HTTPException(status_code=500, detail="Workflow execution failed. No workflow_id.")

        logger.info(
            "Query executed successfully",
            extra={
                "workflow_id": response.workflow_id,
                "correlation_id": response.correlation_id,
                # 👇 NEW: log response conversation_id if present
                "conversation_id": getattr(response, "conversation_id", None),
            },
        )
        return response

    except Exception as e:
        logger.error(f"Query execution failed: {e}", exc_info=True)
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
        status_response: StatusResponse = await orchestration_api.get_status_by_correlation_id(
            correlation_id
        )

        logger.info(
            "Status retrieved",
            extra={
                "workflow_id": status_response.workflow_id,
                "status": status_response.status,
                "correlation_id": correlation_id,
                # if StatusResponse ever includes conversation_id, this will show it
                "conversation_id": getattr(status_response, "conversation_id", None),
            },
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
        logger.error(f"Failed to get status for correlation_id {correlation_id}: {e}", exc_info=True)
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
                        # If you later add conversation_id to the DB + Pydantic model:
                        # conversation_id=workflow_data.get("conversation_id"),
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
        logger.error(f"Failed to retrieve workflow history: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to retrieve workflow history",
                "message": str(e),
                "type": type(e).__name__,
            },
        )
