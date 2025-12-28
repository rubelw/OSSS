from abc import ABC, abstractmethod
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Coroutine
from dataclasses import dataclass
from enum import Enum
import inspect
import time
import random
from typing import cast
from pydantic import BaseModel, Field, ConfigDict
from OSSS.ai.context import AgentContext
from OSSS.ai.exceptions import (
    AgentExecutionError,
    AgentTimeoutError,
    LLMError,
    RetryPolicy,
)
from OSSS.ai.correlation import (
    get_correlation_id,
    get_workflow_id,
)

from OSSS.ai.agents.output_envelope import AgentOutputEnvelope

# Lazy event emission imports to avoid circular import
EVENTS_AVAILABLE = True


async def _maybe_await(x: Any) -> None:
    """Await coroutines; ignore non-awaitables."""
    if inspect.isawaitable(x):
        await x


async def _emit_agent_execution_started(
    workflow_id: str,
    agent_name: str,
    input_context: Dict[str, Any],
    agent_metadata: Optional[Any] = None,
    correlation_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    event_category: Optional[Any] = None,
) -> None:
    """Lazily import and emit agent execution started event."""
    try:
        from OSSS.ai.events import emit_agent_execution_started
        from OSSS.ai.events.types import EventCategory

        # Ensure metadata is always a dict for the event model
        metadata = metadata or {}

        await _maybe_await(
            emit_agent_execution_started(
                workflow_id=workflow_id,
                agent_name=agent_name,
                input_context=input_context,
                agent_metadata=agent_metadata,
                correlation_id=correlation_id,
                metadata=metadata,
                event_category=event_category or EventCategory.EXECUTION,
            )
        )
    except ImportError:
        return
    except Exception as e:
        logging.getLogger(__name__).warning(
            f"Failed to emit agent execution started event: {e}"
        )


def _spawn_if_awaitable(x: Any) -> None:
    """Schedule x if it's awaitable; ignore None/non-awaitables."""
    if x is None:
        return
    if not inspect.isawaitable(x):
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(x)


def _emit_agent_execution_completed(
    workflow_id: str,
    agent_name: str,
    success: bool,
    output_context: Dict[str, Any],
    agent_metadata: Optional[Any] = None,
    execution_time_ms: Optional[float] = None,
    error_message: Optional[str] = None,
    error_type: Optional[str] = None,
    correlation_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    event_category: Optional[Any] = None,
) -> None:
    """Lazily import and emit agent execution completed event (fire-and-forget)."""
    try:
        from OSSS.ai.events import emit_agent_execution_completed
        from OSSS.ai.events.types import EventCategory

        # Ensure metadata is always a dict for the event model
        metadata = metadata or {}

        result = emit_agent_execution_completed(
            workflow_id=workflow_id,
            agent_name=agent_name,
            success=success,
            output_context=output_context,
            agent_metadata=agent_metadata,
            execution_time_ms=execution_time_ms,
            error_message=error_message,
            error_type=error_type,
            correlation_id=correlation_id,
            metadata=metadata,
            event_category=event_category or EventCategory.EXECUTION,
        )

        # If the emitter returned a coroutine/awaitable, schedule it safely.
        # This prevents "coroutine was never awaited" when callers invoke us sync.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and inspect.isawaitable(result):
            loop.create_task(result)

    except ImportError:
        return
    except Exception as e:
        logging.getLogger(__name__).warning(
            f"Failed to emit agent execution completed event: {e}"
        )


# For backward compatibility, make the lazy functions available
emit_agent_execution_started = _emit_agent_execution_started
emit_agent_execution_completed = _emit_agent_execution_completed


class AgentRetryConfig:
    """Configuration for agent retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_backoff: bool = True,
        jitter: bool = True,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_backoff = exponential_backoff
        self.jitter = jitter


class CircuitBreakerState:
    """Simple circuit breaker state for agent execution."""

    def __init__(
        self, failure_threshold: int = 5, recovery_timeout: float = 300.0
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.is_open = False

    def record_success(self) -> None:
        """Record a successful execution."""
        self.failure_count = 0
        self.is_open = False
        self.last_failure_time = None

    def record_failure(self) -> None:
        """Record a failed execution."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)

        if self.failure_count >= self.failure_threshold:
            self.is_open = True

    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        if not self.is_open:
            return True

        if self.last_failure_time:
            time_since_failure = (
                datetime.now(timezone.utc) - self.last_failure_time
            ).total_seconds()
            if time_since_failure >= self.recovery_timeout:
                self.is_open = False
                self.failure_count = 0
                return True

        return False


class NodeType(Enum):
    """Types of nodes in a LangGraph DAG."""

    PROCESSOR = "processor"
    DECISION = "decision"
    TERMINATOR = "terminator"
    AGGREGATOR = "aggregator"
    VALIDATOR = "validator"


class NodeInputSchema(BaseModel):
    """Schema definition for node inputs."""
    name: str = Field(..., description="Name of the input parameter", min_length=1)
    description: str = Field(..., description="Description of the input", min_length=1)
    required: bool = Field(default=True, description="If this input is required")
    type_hint: str = Field(default="Any", description="Type hint for the input parameter")


class NodeOutputSchema(BaseModel):
    """Schema definition for node outputs."""
    name: str = Field(..., description="Name of the output parameter", min_length=1)
    description: str = Field(..., description="Description of the output", min_length=1)
    type_hint: str = Field(default="Any", description="Type hint for the output parameter")


class LangGraphNodeDefinition(BaseModel):
    """LangGraph node definition for an agent."""
    node_id: str
    node_type: NodeType
    description: str
    inputs: List[NodeInputSchema]
    outputs: List[NodeOutputSchema]
    dependencies: List[str] = []
    tags: List[str] = []


class BaseAgent(ABC):
    """Abstract base class for all agents in the OSSS system."""

    def __init__(
        self,
        name: str,
        retry_config: Optional[AgentRetryConfig] = None,
        timeout_seconds: float = 30.0,
        enable_circuit_breaker: bool = True,
    ) -> None:
        self.name: str = name
        self.retry_config = retry_config or AgentRetryConfig()
        self.timeout_seconds = timeout_seconds
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

        # Circuit breaker for this agent
        self.circuit_breaker: Optional[CircuitBreakerState] = None
        if enable_circuit_breaker:
            self.circuit_breaker = CircuitBreakerState()

        # Agent execution statistics
        self.execution_count = 0
        self.success_count = 0
        self.failure_count = 0

        # LangGraph node metadata
        self._node_definition: Optional[LangGraphNodeDefinition] = None

    def _validate_classifications(self, context: AgentContext) -> None:
        """Ensure task_classification and cognitive_classification are set in the context."""
        if not context.task_classification:
            context.task_classification = "task_classification"
        if not context.cognitive_classification:
            context.cognitive_classification = "cognitive_classification"

        if not context.task_classification or not context.cognitive_classification:
            raise ValueError("Both task_classification and cognitive_classification must be set in the context.")

    def _wrap_output(
        self,
        output: str,
        model_version: Optional[str] = None,
        *,
        refined_query: Optional[str] = None,
        **_: Any,
    ) -> AgentOutputEnvelope:
        """
        Normalize agent output into a standard AgentOutputEnvelope.

        Parameters
        ----------
        output:
            Primary string produced by the agent. For RefinerAgent this is
            the refined query string.
        model_version:
            Underlying LLM model identifier (currently ignored).
        refined_query:
            Optional explicit refined_query if a caller provides it. If present,
            it takes precedence over `output`.

        Returns
        -------
        AgentOutputEnvelope
            Standardized envelope with intent/tone/action/content.
        """
        # Prefer an explicit refined_query if provided; fall back to output.
        content = refined_query or output

        return AgentOutputEnvelope(
            intent="refine_query",   # What the agent is doing
            tone="analytical",       # Overall tone for refiner-style work
            sub_tone=None,           # e.g. "query_normalization" if you later want
            action="update",         # We're updating/refining an existing query
            content=content,         # The actual refined query text
        )
    async def run_with_retry(
        self,
        context: AgentContext,
        step_id: Optional[str] = None,
    ) -> AgentContext:
        """
        Execute the agent with retry logic, timeout, and circuit breaker pattern.

        Guarantees:
          - Returns an AgentContext on success
          - Raises AgentExecutionError / AgentTimeoutError / LLMError on failure
          - Never returns None
        """
        # --- Basic validation ---
        if not isinstance(context, AgentContext):
            raise TypeError(f"{self.name}.run_with_retry expected AgentContext, got {type(context)}")

        # Ensure classifications exist at start (optional enforcement)
        self._validate_classifications(context)

        # Ensure execution_state is a dict
        if not isinstance(getattr(context, "execution_state", None), dict):
            context.execution_state = {}

        # Ensure execution_metadata is a dict
        if not isinstance(getattr(context, "execution_metadata", None), dict):
            context.execution_metadata = {}

        exec_state = context.execution_state

        # Correlation / workflow / execution ids
        workflow_id = get_workflow_id() or exec_state.get("workflow_id") or str(uuid.uuid4())
        correlation_id = get_correlation_id() or exec_state.get("correlation_id") or None
        execution_id = exec_state.get("execution_id") or str(uuid.uuid4())

        exec_state.setdefault("workflow_id", workflow_id)
        exec_state.setdefault("correlation_id", correlation_id)
        exec_state.setdefault("execution_id", execution_id)
        exec_state.setdefault("current_agent", self.name)

        input_snapshot: Dict[str, Any] = {
            "query": context.query,
            "execution_state": exec_state,
        }

        # Emit "started" event (awaited)
        await emit_agent_execution_started(
            workflow_id=workflow_id,
            agent_name=self.name,
            input_context=input_snapshot,
            agent_metadata=None,
            correlation_id=correlation_id,
            metadata={"step_id": step_id} if step_id else None,
            event_category=None,
        )

        # --- Retry loop ---
        attempt = 0
        last_error: Optional[Exception] = None

        while attempt <= self.retry_config.max_retries:
            if self.circuit_breaker and not self.circuit_breaker.can_execute():
                msg = f"Circuit breaker open for agent '{self.name}'. Refusing execution."
                self.logger.error(msg)
                raise AgentExecutionError(self.name, msg)

            start_time = time.time()
            self.execution_count += 1

            try:
                self.logger.info(
                    f"[{self.name}] Attempt {attempt + 1} of {self.retry_config.max_retries + 1}"
                )

                # --- Run agent with timeout ---
                result_ctx = await asyncio.wait_for(
                    self.run(context),
                    timeout=self.timeout_seconds,
                )

                # --- Validate result ---
                if not isinstance(result_ctx, AgentContext):
                    raise AgentExecutionError(
                        self.name,
                        f"{self.name}.run must return AgentContext, got {type(result_ctx)}",
                    )

                if not isinstance(result_ctx.execution_state, dict):
                    result_ctx.execution_state = {}

                # -----------------------------------------------------------------
                # 🔧 **CRITICAL FIX — MERGE execution_state, DO NOT overwrite**
                #
                # This ensures that classifier results and routing hints survive
                # into refiner -> data_query -> final nodes.
                #
                # Order:
                #   - keep anything written earlier in context.execution_state
                #   - apply new values returned by result_ctx.execution_state
                #   - both contexts now reference same dict
                # -----------------------------------------------------------------
                merged_state = context.execution_state

                for k, v in result_ctx.execution_state.items():
                    merged_state[k] = v  # merge forward

                # Keep both referencing same dictionary
                result_ctx.execution_state = merged_state
                context.execution_state = merged_state
                exec_state = merged_state
                # -----------------------------------------------------------------

                # --- mark success ---
                self.success_count += 1
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()

                elapsed_ms = (time.time() - start_time) * 1000.0

                output_snapshot: Dict[str, Any] = {
                    "query": result_ctx.query,
                    "execution_state": result_ctx.execution_state,
                    "agent_outputs": getattr(result_ctx, "agent_outputs", {}),
                }

                # Emit "completed" success
                _emit_agent_execution_completed(
                    workflow_id=workflow_id,
                    agent_name=self.name,
                    success=True,
                    output_context=output_snapshot,
                    agent_metadata=None,
                    execution_time_ms=elapsed_ms,
                    error_message=None,
                    error_type=None,
                    correlation_id=correlation_id,
                    metadata={"step_id": step_id} if step_id else None,
                    event_category=None,
                )

                return result_ctx

            except asyncio.TimeoutError as e:
                self.failure_count += 1
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()

                elapsed_ms = (time.time() - start_time) * 1000.0
                msg = f"{self.name} timed out after {self.timeout_seconds}s"
                # include agent_name as required by AgentTimeoutError
                err = AgentTimeoutError(self.name, msg)
                last_error = err
                self.logger.error(msg)

                _emit_agent_execution_completed(
                    workflow_id=workflow_id,
                    agent_name=self.name,
                    success=False,
                    output_context={"query": context.query, "execution_state": exec_state},
                    agent_metadata=None,
                    execution_time_ms=elapsed_ms,
                    error_message=str(err),
                    error_type=err.__class__.__name__,
                    correlation_id=correlation_id,
                    metadata={"step_id": step_id, "attempt": attempt + 1},
                    event_category=None,
                )

            except (LLMError, AgentExecutionError) as e:
                self.failure_count += 1
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()

                elapsed_ms = (time.time() - start_time) * 1000.0
                last_error = e
                self.logger.error(f"{self.name} failed with known error type: {e}")

                _emit_agent_execution_completed(
                    workflow_id=workflow_id,
                    agent_name=self.name,
                    success=False,
                    output_context={"query": context.query, "execution_state": exec_state},
                    agent_metadata=None,
                    execution_time_ms=elapsed_ms,
                    error_message=str(e),
                    error_type=e.__class__.__name__,
                    correlation_id=correlation_id,
                    metadata={"step_id": step_id, "attempt": attempt + 1},
                    event_category=None,
                )

            except Exception as e:
                # Wrap any unknown errors
                self.failure_count += 1
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()

                elapsed_ms = (time.time() - start_time) * 1000.0
                wrapped = AgentExecutionError(
                    self.name,
                    f"{self.name} unexpected error: {e}",
                )
                last_error = wrapped
                self.logger.exception(f"{self.name} unexpected error")

                _emit_agent_execution_completed(
                    workflow_id=workflow_id,
                    agent_name=self.name,
                    success=False,
                    output_context={"query": context.query, "execution_state": exec_state},
                    agent_metadata=None,
                    execution_time_ms=elapsed_ms,
                    error_message=str(wrapped),
                    error_type=wrapped.__class__.__name__,
                    correlation_id=correlation_id,
                    metadata={"step_id": step_id, "attempt": attempt + 1},
                    event_category=None,
                )

            # Decide whether to retry
            attempt += 1
            if attempt > self.retry_config.max_retries:
                break

            # Backoff delay
            delay = self.retry_config.base_delay
            if self.retry_config.exponential_backoff:
                delay *= 2 ** (attempt - 1)
            delay = min(delay, self.retry_config.max_delay)
            if self.retry_config.jitter:
                delay *= random.uniform(0.5, 1.5)

            self.logger.info(
                f"[{self.name}] Retrying in {delay:.2f}s "
                f"(attempt {attempt + 1}/{self.retry_config.max_retries + 1})"
            )
            await asyncio.sleep(delay)




        # Out of retries → raise last error
        if last_error:
            raise last_error
        raise AgentExecutionError(
            self.name,
            f"{self.name} failed with unknown error and no retries recorded",
        )

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentContext:
        """
        Execute the agent asynchronously using the provided context.
        """
        pass  # pragma: no cover
