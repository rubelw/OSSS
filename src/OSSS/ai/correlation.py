import uuid
from contextvars import ContextVar
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator, Dict, Any
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ConfigDict
from .observability import get_logger

logger = get_logger(__name__)

# Context variables for correlation tracking
context_correlation_id: ContextVar[Optional[str]] = ContextVar(
    "correlation_id", default=None
)
context_workflow_id: ContextVar[Optional[str]] = ContextVar("workflow_id", default=None)
context_parent_span_id: ContextVar[Optional[str]] = ContextVar(
    "parent_span_id", default=None
)
context_trace_metadata: ContextVar[Dict[str, Any]] = ContextVar(
    "trace_metadata", default={}
)


class CorrelationContext(BaseModel):
    """
    Correlation context for tracing requests through the system.

    Migrated from dataclass to Pydantic BaseModel for enhanced validation,
    serialization, and integration with the OSSS Pydantic ecosystem.

    Provides access to correlation information that automatically
    propagates through async execution chains.
    """

    correlation_id: str = Field(
        ...,
        description="Unique correlation identifier for tracing across services",
        min_length=1,
        max_length=200,
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    )
    workflow_id: str = Field(
        ...,
        description="Unique workflow identifier for the current execution",
        min_length=1,
        max_length=200,
        json_schema_extra={"example": "wf-abc123-def456"},
    )
    parent_span_id: Optional[str] = Field(
        None,
        description="Parent span ID for nested operation tracing",
        max_length=200,
        json_schema_extra={"example": "span-xyz789"},
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional trace metadata and context information",
        json_schema_extra={
            "example": {"service_name": "osss", "operation": "agent_execution"}
        },
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this correlation context was created (UTC)",
        json_schema_extra={"example": "2024-01-01T12:00:00Z"},
    )

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    def to_dict(self) -> Dict[str, Any]:
        data = self.model_dump(mode="json")
        data["created_at"] = self.created_at.isoformat()
        logger.debug(f"Converted CorrelationContext to dict: {data}")
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CorrelationContext":
        context = cls.model_validate(data)
        logger.debug(f"Created CorrelationContext from dict: {context.to_dict()}")
        return context


@asynccontextmanager
async def trace(
    correlation_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[CorrelationContext, None]:
    """
    Context manager for explicit correlation control.

    Sets correlation context for the duration of the async context and
    automatically restores the previous context when exiting.
    """
    current_correlation = correlation_id or str(uuid.uuid4())
    current_workflow = workflow_id or str(uuid.uuid4())
    current_metadata = metadata or {}

    prev_correlation = context_correlation_id.get(None)
    prev_workflow = context_workflow_id.get(None)
    prev_parent_span = context_parent_span_id.get(None)
    prev_metadata = context_trace_metadata.get({})

    # Set new context
    correlation_token = context_correlation_id.set(current_correlation)
    workflow_token = context_workflow_id.set(current_workflow)
    parent_span_token = context_parent_span_id.set(parent_span_id)
    metadata_token = context_trace_metadata.set(current_metadata)

    context = CorrelationContext(
        correlation_id=current_correlation,
        workflow_id=current_workflow,
        parent_span_id=parent_span_id,
        metadata=current_metadata,
    )

    logger.debug(
        f"Starting trace context: correlation_id={current_correlation}, "
        f"workflow_id={current_workflow}, parent_span_id={parent_span_id}, "
        f"metadata={current_metadata}"
    )

    try:
        yield context
    finally:
        # Restore previous context
        context_correlation_id.reset(correlation_token)
        context_workflow_id.reset(workflow_token)
        context_parent_span_id.reset(parent_span_token)
        context_trace_metadata.reset(metadata_token)

        logger.debug(f"Restored trace context: correlation_id={prev_correlation}")


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID from context."""
    correlation_id = context_correlation_id.get(None)
    logger.debug(f"Retrieved correlation_id: {correlation_id}")
    return correlation_id


def get_workflow_id() -> Optional[str]:
    """Get the current workflow ID from context."""
    workflow_id = context_workflow_id.get(None)
    logger.debug(f"Retrieved workflow_id: {workflow_id}")
    return workflow_id


def get_parent_span_id() -> Optional[str]:
    """Get the current parent span ID from context."""
    parent_span_id = context_parent_span_id.get(None)
    logger.debug(f"Retrieved parent_span_id: {parent_span_id}")
    return parent_span_id


def get_trace_metadata() -> Dict[str, Any]:
    """Get the current trace metadata from context."""
    trace_metadata = context_trace_metadata.get({})
    logger.debug(f"Retrieved trace metadata: {trace_metadata}")
    return trace_metadata


def get_current_context() -> Optional[CorrelationContext]:
    """
    Get the current correlation context if available.
    """
    correlation_id = get_correlation_id()
    workflow_id = get_workflow_id()

    if not correlation_id or not workflow_id:
        logger.debug("No correlation context found")
        return None

    context = CorrelationContext(
        correlation_id=correlation_id,
        workflow_id=workflow_id,
        parent_span_id=get_parent_span_id(),
        metadata=get_trace_metadata(),
    )
    logger.debug(f"Retrieved current context: {context.to_dict()}")
    return context


def ensure_correlation_context() -> CorrelationContext:
    """
    Ensure a correlation context exists, creating one if necessary.
    """
    current = get_current_context()
    if current:
        logger.debug("Correlation context already exists")
        return current

    correlation_id = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())

    context_correlation_id.set(correlation_id)
    context_workflow_id.set(workflow_id)
    context_trace_metadata.set({})

    logger.debug(f"Created new correlation context: {correlation_id}")
    return CorrelationContext(
        correlation_id=correlation_id,
        workflow_id=workflow_id,
        metadata={},
    )


def create_child_span(
    operation_name: str, metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create a child span ID for nested operations.
    """
    current_correlation = get_correlation_id()
    current_span = get_parent_span_id()

    child_span_id = f"{operation_name}:{uuid.uuid4().hex[:8]}"
    current_metadata = get_trace_metadata().copy()
    current_metadata.update(
        {
            "current_span": child_span_id,
            "parent_span": current_span,
            "operation": operation_name,
            **(metadata or {}),
        }
    )

    context_parent_span_id.set(child_span_id)
    context_trace_metadata.set(current_metadata)

    logger.debug(
        f"Created child span: {child_span_id} (parent: {current_span}, "
        f"correlation: {current_correlation})"
    )

    return child_span_id


def add_trace_metadata(key: str, value: Any) -> None:
    """
    Add metadata to the current trace context.
    """
    current_metadata = get_trace_metadata().copy()
    current_metadata[key] = value
    context_trace_metadata.set(current_metadata)

    logger.debug(f"Added trace metadata: {key} = {value}")


def get_correlation_headers() -> Dict[str, str]:
    """
    Get correlation information as HTTP headers.
    """
    correlation_id = get_correlation_id()
    workflow_id = get_workflow_id()
    parent_span_id = get_parent_span_id()

    headers = {}

    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id
    if workflow_id:
        headers["X-Workflow-ID"] = workflow_id
    if parent_span_id:
        headers["X-Parent-Span-ID"] = parent_span_id

    logger.debug(f"Generated correlation headers: {headers}")
    return headers


async def propagate_correlation(func: Any, *args: Any, **kwargs: Any) -> Any:
    """
    Ensure correlation context propagates to async functions.
    """
    current_context = get_current_context()

    if current_context:
        logger.debug("Existing correlation context found, proceeding with function call")
        return await func(*args, **kwargs)
    else:
        logger.debug("No correlation context, creating one for this operation")
        async with trace() as ctx:
            return await func(*args, **kwargs)


async def with_correlation(
    correlation_id: str,
    workflow_id: Optional[str] = None,
    func: Any = None,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Execute a function with explicit correlation context.
    """
    async with trace(correlation_id=correlation_id, workflow_id=workflow_id):
        logger.debug(f"Executing with correlation: {correlation_id}")
        if func:
            return await func(*args, **kwargs)
        else:
            return get_current_context()


def is_traced() -> bool:
    """
    Check if we're currently in a trace context.
    """
    is_traced = get_correlation_id() is not None
    logger.debug(f"Is traced: {is_traced}")
    return is_traced
