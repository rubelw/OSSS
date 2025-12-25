from abc import ABC, abstractmethod
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Coroutine
from dataclasses import dataclass
from enum import Enum
import inspect


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
# Events will be imported at runtime when needed
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

# Make event emission functions available at module level for testing
__all__ = [
    "BaseAgent",
    "AgentRetryConfig",
    "CircuitBreakerState",
    "NodeType",
    "NodeInputSchema",
    "NodeOutputSchema",
    "LangGraphNodeDefinition",
    "emit_agent_execution_started",
    "emit_agent_execution_completed",
]


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

    PROCESSOR = "processor"  # Standard processing node
    DECISION = "decision"  # Decision/routing node
    TERMINATOR = "terminator"  # End/output node
    AGGREGATOR = "aggregator"  # Combines multiple inputs
    VALIDATOR = "validator"  # Quality assurance checkpoint


class NodeInputSchema(BaseModel):
    """
    Schema definition for node inputs.

    Migrated from dataclass to Pydantic BaseModel for enhanced validation,
    serialization, and integration with the OSSS Pydantic ecosystem.
    """

    name: str = Field(
        ...,
        description="Name of the input parameter",
        min_length=1,
        max_length=100,
        json_schema_extra={"example": "context"},
    )
    description: str = Field(
        ...,
        description="Human-readable description of the input",
        min_length=1,
        max_length=500,
        json_schema_extra={"example": "Agent context containing query and state"},
    )
    required: bool = Field(
        default=True,
        description="Whether this input is required for node execution",
        json_schema_extra={"example": True},
    )
    type_hint: str = Field(
        default="Any",
        description="Type hint for the input parameter",
        min_length=1,
        max_length=100,
        json_schema_extra={"example": "AgentContext"},
    )

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )


class NodeOutputSchema(BaseModel):
    """
    Schema definition for node outputs.

    Migrated from dataclass to Pydantic BaseModel for enhanced validation,
    serialization, and integration with the OSSS Pydantic ecosystem.
    """

    name: str = Field(
        ...,
        description="Name of the output parameter",
        min_length=1,
        max_length=100,
        json_schema_extra={"example": "context"},
    )
    description: str = Field(
        ...,
        description="Human-readable description of the output",
        min_length=1,
        max_length=500,
        json_schema_extra={"example": "Updated context after agent processing"},
    )
    type_hint: str = Field(
        default="Any",
        description="Type hint for the output parameter",
        min_length=1,
        max_length=100,
        json_schema_extra={"example": "AgentContext"},
    )

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )


class LangGraphNodeDefinition(BaseModel):
    """
    Complete LangGraph node definition for an agent.

    Migrated from dataclass to Pydantic BaseModel for enhanced validation,
    serialization, and integration with the OSSS Pydantic ecosystem.
    """

    node_id: str = Field(
        ...,
        description="Unique identifier for the node",
        min_length=1,
        max_length=100,
        json_schema_extra={"example": "refiner"},
    )
    node_type: NodeType = Field(
        ...,
        description="Type of node in the LangGraph DAG",
        json_schema_extra={"example": "processor"},
    )
    description: str = Field(
        ...,
        description="Human-readable description of the node",
        min_length=1,
        max_length=500,
        json_schema_extra={"example": "Refiner agent for query processing"},
    )
    inputs: List[NodeInputSchema] = Field(
        ...,
        description="List of input schemas for this node",
        json_schema_extra={
            "example": [{"name": "context", "description": "Input context"}]
        },
    )
    outputs: List[NodeOutputSchema] = Field(
        ...,
        description="List of output schemas for this node",
        json_schema_extra={
            "example": [{"name": "context", "description": "Output context"}]
        },
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of node IDs this node depends on",
        json_schema_extra={"example": ["refiner", "critic"]},
    )
    tags: List[str] = Field(
        default_factory=list,
        description="List of tags for categorization",
        json_schema_extra={"example": ["agent", "processor"]},
    )

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary representation.

        Maintains backward compatibility with existing code while leveraging
        Pydantic's enhanced serialization capabilities.
        """
        # Use Pydantic's model_dump for better serialization
        data = self.model_dump()

        # Convert node_type enum to string value for compatibility
        data["node_type"] = self.node_type.value

        # Convert input/output schemas to the expected format
        data["inputs"] = [
            {
                "name": inp.name,
                "description": inp.description,
                "required": inp.required,
                "type": inp.type_hint,
            }
            for inp in self.inputs
        ]
        data["outputs"] = [
            {
                "name": out.name,
                "description": out.description,
                "type": out.type_hint,
            }
            for out in self.outputs
        ]

        return data


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the OSSS system.

    Enhanced with LangGraph-compatible features including agent-local retry policies,
    circuit breaker patterns, trace metadata, and error handling designed for
    future DAG-based orchestration.

    Parameters
    ----------
    name : str
        The name of the agent.
    retry_config : AgentRetryConfig, optional
        Retry configuration for this agent. If None, uses default settings.
    timeout_seconds : float, optional
        Agent execution timeout in seconds. Default is 30.0.
    enable_circuit_breaker : bool, optional
        Whether to enable circuit breaker pattern. Default is True.
    """

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
        self.logger = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

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


    def _get_exec_info(self, ctx: AgentContext) -> Any:
        """Best-effort fetch of per-agent execution info from context."""
        try:
            return ctx.get_agent_execution(self.name)
        except Exception:
            return None

    def _is_started(self, exec_info: Any) -> bool:
        # started flag if present
        started = self._exec_get(exec_info, "started", None)
        if started is not None:
            return bool(started)

        # Some implementations track state strings
        status = self._exec_get(exec_info, "status", None)
        if isinstance(status, str):
            return status.lower() in {"started", "running", "in_progress", "executing"}

        # Fallback: if step_id exists, treat as started
        step_id = self._exec_get(exec_info, "step_id", None)
        return step_id is not None

    def _is_completed(self, exec_info: Any) -> bool:
        completed = self._exec_get(exec_info, "completed", None)
        if completed is not None:
            return bool(completed)

        status = self._exec_get(exec_info, "status", None)
        if isinstance(status, str):
            return status.lower() in {"completed", "failed", "success", "error"}

        return False


    @staticmethod
    def _exec_get(exec_info: Any, key: str, default: Any = None) -> Any:
        if exec_info is None:
            return default
        # dict-shaped
        if isinstance(exec_info, dict):
            return exec_info.get(key, default)
        # object-shaped
        return getattr(exec_info, key, default)

    def _wrap_output(
            self,
            output: str | None = None,
            *,
            intent: str | None = None,
            tone: str | None = None,
            action: str | None = None,
            sub_tone: str | None = None,
            content: str | None = None,
            **_: Any,
    ) -> dict:
        # Always populate a stable envelope shape
        return {
            "output": output,
            "content": content if content is not None else output,
            "intent": intent,
            "tone": tone,
            "action": action,  # ✅ MAKE SURE THIS EXISTS
            "sub_tone": sub_tone,
            "agent": getattr(self, "name", None),
        }



    def generate_step_id(self) -> str:
        """Generate a unique step ID for this execution."""
        return f"{self.name.lower()}_{uuid.uuid4().hex[:8]}"

    async def run_with_retry(
            self, context: AgentContext, step_id: Optional[str] = None
    ) -> AgentContext:
        """
        Execute the agent with retry logic, timeout, and circuit breaker pattern.

        BaseAgent is the *single source of truth* for agent execution events:
        - emits started exactly once
        - emits completed exactly once
        - emits timeout/failure completed events in exception paths
        """
        # Hard guard: must be an instance, not the class
        if isinstance(context, type) or not isinstance(context, AgentContext):
            raise AgentExecutionError(
                message=f"Invalid context passed to agent '{self.name}': expected AgentContext instance, got {type(context)}",
                agent_name=self.name,
                error_code="invalid_agent_context",
                step_id=step_id,
                context={"received_type": str(type(context))},
            )

        step_id = step_id or self.generate_step_id()
        start_time = datetime.now(timezone.utc)

        # Check circuit breaker
        if self.circuit_breaker and not self.circuit_breaker.can_execute():
            failure_time = self.circuit_breaker.last_failure_time
            time_remaining = self.circuit_breaker.recovery_timeout
            if failure_time:
                elapsed = (datetime.now(timezone.utc) - failure_time).total_seconds()
                time_remaining = max(0.0, self.circuit_breaker.recovery_timeout - elapsed)

            raise AgentExecutionError(
                message=f"Circuit breaker open for agent '{self.name}'",
                agent_name=self.name,
                error_code="circuit_breaker_open",
                context={
                    "failure_count": self.circuit_breaker.failure_count,
                    "time_remaining_seconds": time_remaining,
                },
                step_id=step_id,
            )

        self.execution_count += 1

        # -----------------------------------------------------------------------
        # Emit "started" exactly once per step (guards prevent retry spam)
        # -----------------------------------------------------------------------
        if True:
            try:
                exec_info0 = None
                try:
                    exec_info0 = context.get_agent_execution(self.name)
                except Exception:
                    exec_info0 = None

                started0 = self._exec_get(exec_info0, "started", None)
                status0 = self._exec_get(exec_info0, "status", None)
                already_started = (
                        (started0 is not None and bool(started0))
                        or (isinstance(status0, str) and status0.lower() in {"started", "running", "in_progress",
                                                                             "executing"})
                        or (self._exec_get(exec_info0, "step_id", None) is not None)
                )

                if already_started:
                    self.logger.debug(
                        f"[{self.name}] Skipping started event; already started in context (step: {step_id})"
                    )
                else:
                    from OSSS.ai.agents.registry import get_agent_registry

                    registry = get_agent_registry()
                    try:
                        agent_metadata = registry.get_metadata(self.name)
                    except ValueError:
                        agent_metadata = None

                    _spawn_if_awaitable(
                        emit_agent_execution_started(
                            workflow_id=get_workflow_id() or step_id,
                            agent_name=self.name,
                            input_context={
                                "step_id": step_id,
                                "execution_count": self.execution_count,
                                "input_tokens": getattr(context, "token_count", 0),
                                "context_size": len(str(context)),
                            },
                            agent_metadata=agent_metadata,
                            correlation_id=get_correlation_id(),
                            metadata={
                                "retry_config": {
                                    "max_retries": self.retry_config.max_retries,
                                    "timeout_seconds": self.timeout_seconds,
                                },
                                "circuit_breaker_enabled": self.circuit_breaker is not None,
                            },
                        )
                    )
            except Exception as e:
                self.logger.warning(f"Failed to emit agent execution started event: {e}")

        retries = 0
        last_exception: Optional[Exception] = None


        while retries <= self.retry_config.max_retries:
            try:
                self.logger.info(
                    f"[{self.name}] Starting execution (step: {step_id}, attempt: {retries + 1})"
                )

                # -------------------------------------------------------------------
                # ✅ RAG gating + population (ONLY for output agent, run once per step)
                # -------------------------------------------------------------------
                try:
                    exec_state = getattr(context, "execution_state", None)

                    is_output_agent = (self.name or "").strip().lower() == "output"

                    if (
                            is_output_agent
                            and isinstance(exec_state, dict)
                            and exec_state.get("rag_enabled") is True
                    ):
                        # prevent re-populating on retries
                        if not exec_state.get("_rag_populated"):
                            exec_state["_rag_populated"] = True  # set early to avoid duplicate work

                            # Optional: clear any stale values
                            exec_state.pop("rag_context", None)
                            exec_state.pop("rag_hits", None)
                            exec_state.pop("rag_meta", None)

                            # --- CALL YOUR RETRIEVER HERE ---
                            # Use context.query (for output node this should already be refined,
                            # because convert_state_to_context pulls state["query"]).
                            query_for_rag = (context.query or "").strip()

                            rag_context = ""
                            rag_hits = []
                            rag_meta = {"query_used": query_for_rag}

                            # Example skeleton (replace with your real retriever):
                            # from OSSS.ai.rag.service import RagService
                            # svc = RagService(...)
                            # retrieved = await svc.retrieve(query=query_for_rag, top_k=exec_state.get("rag_top_k", 8))
                            # rag_context = retrieved.context_text
                            # rag_hits = retrieved.hits
                            # rag_meta = retrieved.meta

                            exec_state["rag_context"] = rag_context
                            exec_state["rag_hits"] = rag_hits
                            exec_state["rag_meta"] = rag_meta

                            self.logger.debug(
                                f"[{self.name}] RAG populated for output agent: hits={len(rag_hits) if isinstance(rag_hits, list) else 0}"
                            )
                except Exception as rag_e:
                    # Never block agent execution if retrieval fails
                    try:
                        if isinstance(getattr(context, "execution_state", None), dict):
                            context.execution_state["rag_error"] = str(rag_e)
                    except Exception:
                        pass
                    self.logger.warning(f"[{self.name}] RAG population failed (continuing without RAG): {rag_e}")

                # Execute with timeout
                result = await asyncio.wait_for(
                    self._execute_with_context(context, step_id),
                    timeout=self.timeout_seconds,
                )

                # Use returned context for subsequent checks/logs
                ctx = result

                # Determine success/completion from context exec_info (dict or object)
                exec_info = None
                try:
                    exec_info = ctx.get_agent_execution(self.name)
                except Exception:
                    exec_info = None

                completed_before = bool(self._exec_get(exec_info, "completed", False))
                success_val = self._exec_get(exec_info, "success", None)
                success = bool(success_val) if success_val is not None else True

                # Only mark completion if not already completed in context
                if not completed_before:
                    try:
                        ctx.complete_agent_execution(self.name, success=success)
                    except Exception:
                        pass

                # -------------------------------------------------------------------
                # Ensure per-agent output envelope is persisted for API response
                # -------------------------------------------------------------------
                try:
                    exec_state = getattr(ctx, "execution_state", None)
                    if isinstance(exec_state, dict):
                        meta = exec_state.get("agent_output_meta")
                        if not isinstance(meta, dict):
                            meta = {}
                            exec_state["agent_output_meta"] = meta

                        canon = (self.name or "").strip().lower()

                        # Only synthesize if agent didn't already store an envelope
                        if canon and (canon not in meta or not isinstance(meta.get(canon), dict)):
                            agent_output = ""
                            try:
                                agent_output = (
                                        (getattr(ctx, "agent_outputs", {}) or {}).get(canon)
                                        or (getattr(ctx, "agent_outputs", {}) or {}).get(self.name, "")
                                        or ""
                                )
                            except Exception:
                                agent_output = ""

                            meta[canon] = {
                                "agent": canon,
                                "intent": None,
                                "tone": None,
                                "action": "read",  # default if agent didn't set it
                                "sub_tone": None,
                                "output": agent_output,
                                "content": agent_output,
                            }

                            self.logger.debug(
                                f"[{self.name}] Synthesized output envelope (action=read) for API meta"
                            )
                except Exception as env_e:
                    self.logger.debug(
                        f"[{self.name}] Failed to synthesize/store output envelope: {env_e}"
                    )

                execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()

                # Metrics reflect real success
                if success:
                    self.success_count += 1
                    if self.circuit_breaker:
                        self.circuit_breaker.record_success()
                else:
                    self.failure_count += 1
                    if self.circuit_breaker:
                        self.circuit_breaker.record_failure()

                self.logger.info(
                    f"[{self.name}] Execution {'successful' if success else 'failed'} "
                    f"(step: {step_id}, time: {execution_time:.2f}s, attempt: {retries + 1})"
                )

                # -------------------------------------------------------------------
                # Emit "completed" exactly once (guard against double emit)
                # -------------------------------------------------------------------
                if True:
                    try:
                        from OSSS.ai.agents.registry import get_agent_registry

                        registry = get_agent_registry()
                        try:
                            agent_metadata = registry.get_metadata(self.name)
                        except ValueError:
                            agent_metadata = None

                        exec_info_done = None
                        try:
                            exec_info_done = ctx.get_agent_execution(self.name)
                        except Exception:
                            exec_info_done = None

                        completed_flag = self._exec_get(exec_info_done, "completed", None)
                        status_done = self._exec_get(exec_info_done, "status", None)
                        already_completed = (
                                (completed_flag is not None and bool(completed_flag))
                                or (isinstance(status_done, str) and status_done.lower() in {"completed", "failed",
                                                                                             "success", "error"})
                        )

                        if already_completed and completed_before:
                            # If it was already completed before we got here, don't emit
                            self.logger.debug(
                                f"[{self.name}] Skipping completed event; already completed in context (step: {step_id})"
                            )
                        else:
                            agent_output: str = (getattr(ctx, "agent_outputs", {}) or {}).get(self.name, "")
                            token_usage = ctx.get_agent_token_usage(self.name)

                            emit_agent_execution_completed(
                                workflow_id=get_workflow_id() or step_id,
                                agent_name=self.name,
                                success=success,
                                output_context={
                                    "step_id": step_id,
                                    "execution_time_seconds": execution_time,
                                    "attempts_used": retries + 1,
                                    "agent_output": agent_output[:1000] if agent_output else "",
                                    "output_length": len(agent_output) if agent_output else 0,
                                    "input_tokens": token_usage["input_tokens"],
                                    "output_tokens": token_usage["output_tokens"],
                                    "total_tokens": token_usage["total_tokens"],
                                    "context_size": len(str(ctx)),
                                },
                                agent_metadata=agent_metadata,
                                correlation_id=get_correlation_id(),
                                execution_time_ms=execution_time * 1000,
                                metadata={
                                    "success_count": self.success_count,
                                    "failure_count": self.failure_count,
                                    "total_executions": self.execution_count,
                                    "circuit_breaker_state": (
                                        "closed"
                                        if not self.circuit_breaker or not self.circuit_breaker.is_open
                                        else "open"
                                    ),
                                    "completed_already_in_context": completed_before,
                                },
                            )
                    except Exception as e:
                        self.logger.warning(f"Failed to emit agent execution completed event: {e}")

                # Log trace
                try:
                    ctx.log_trace(
                        self.name,
                        input_data={"step_id": step_id, "attempt": retries + 1},
                        output_data={
                            "success": success,
                            "execution_time_seconds": execution_time,
                            "attempts_used": retries + 1,
                        },
                    )
                except Exception:
                    pass

                return ctx

            except asyncio.TimeoutError as e:
                last_exception = e
                self.logger.warning(
                    f"[{self.name}] Timeout after {self.timeout_seconds}s (step: {step_id})"
                )

                if retries < self.retry_config.max_retries:
                    await self._handle_retry_delay(retries)
                    retries += 1
                    continue

                # Final timeout failure
                self.failure_count += 1
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()

                if True:
                    try:
                        from OSSS.ai.agents.registry import get_agent_registry

                        registry = get_agent_registry()
                        try:
                            agent_metadata = registry.get_metadata(self.name)
                        except ValueError:
                            agent_metadata = None

                        emit_agent_execution_completed(
                            workflow_id=get_workflow_id() or step_id,
                            agent_name=self.name,
                            success=False,
                            output_context={
                                "step_id": step_id,
                                "attempts_made": retries + 1,
                                "max_retries": self.retry_config.max_retries,
                                "timeout_seconds": self.timeout_seconds,
                                "error_type": "AgentTimeoutError",
                                "error_message": f"Agent timed out after {self.timeout_seconds}s",
                            },
                            agent_metadata=agent_metadata,
                            correlation_id=get_correlation_id(),
                            error_message=f"Agent timed out after {self.timeout_seconds}s",
                            error_type="AgentTimeoutError",
                            metadata={
                                "failure_count": self.failure_count,
                                "total_executions": self.execution_count,
                                "circuit_breaker_state": (
                                    "open"
                                    if self.circuit_breaker and self.circuit_breaker.is_open
                                    else "closed"
                                ),
                            },
                        )
                    except Exception as emit_e:
                        self.logger.warning(f"Failed to emit agent timeout event: {emit_e}")

                raise AgentTimeoutError(
                    agent_name=self.name,
                    timeout_seconds=self.timeout_seconds,
                    step_id=step_id,
                    context={
                        "attempts_made": retries + 1,
                        "max_retries": self.retry_config.max_retries,
                    },
                    cause=e,
                )

            except Exception as e:
                last_exception = e
                self.logger.warning(f"[{self.name}] Execution failed: {e} (step: {step_id})")

                should_retry = self._should_retry_exception(e)
                if should_retry and retries < self.retry_config.max_retries:
                    await self._handle_retry_delay(retries)
                    retries += 1
                    continue

                # Final failure
                self.failure_count += 1
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()

                if True:
                    try:
                        from OSSS.ai.agents.registry import get_agent_registry

                        registry = get_agent_registry()
                        try:
                            agent_metadata = registry.get_metadata(self.name)
                        except ValueError:
                            agent_metadata = None

                        emit_agent_execution_completed(
                            workflow_id=get_workflow_id() or step_id,
                            agent_name=self.name,
                            success=False,
                            output_context={
                                "step_id": step_id,
                                "attempts_made": retries + 1,
                                "max_retries": self.retry_config.max_retries,
                                "error_type": type(e).__name__,
                                "error_message": str(e),
                            },
                            agent_metadata=agent_metadata,
                            correlation_id=get_correlation_id(),
                            error_message=str(e),
                            error_type=type(e).__name__,
                            metadata={
                                "failure_count": self.failure_count,
                                "total_executions": self.execution_count,
                                "circuit_breaker_state": (
                                    "open"
                                    if self.circuit_breaker and self.circuit_breaker.is_open
                                    else "closed"
                                ),
                            },
                        )
                    except Exception as emit_e:
                        self.logger.warning(
                            f"Failed to emit agent execution failed event: {emit_e}"
                        )

                if isinstance(e, (AgentExecutionError, LLMError)):
                    raise

                raise AgentExecutionError(
                    message=f"Agent execution failed: {str(e)}",
                    agent_name=self.name,
                    error_code="agent_execution_failed",
                    step_id=step_id,
                    context={
                        "attempts_made": retries + 1,
                        "max_retries": self.retry_config.max_retries,
                        "original_exception": str(e),
                    },
                    cause=e,
                )

        raise AgentExecutionError(
            message=f"Agent execution failed after {retries} attempts",
            agent_name=self.name,
            step_id=step_id,
            cause=last_exception,
        )

    def _already_completed(self, ctx: AgentContext) -> bool:
        try:
            status = (ctx.agent_execution_status or {}).get(self.name.lower())
            return status in {"completed", "failed"}
        except Exception:
            return False

    async def _execute_with_context(self, context: AgentContext, step_id: str) -> AgentContext:
        """
        Internal method that wraps the actual agent execution with context metadata.

        NOTE: BaseAgent.run_with_retry is the *single source of truth* for
        completion events and completion status bookkeeping. This wrapper only:
        - marks start in the context
        - writes execution_state metadata
        - calls the concrete agent's run()
        - returns/raises
        """
        # Start execution tracking in context (ok if no-op)
        try:
            context.start_agent_execution(self.name, step_id)
        except Exception:
            pass

        # Add step metadata to execution_state for trace tracking
        try:
            step_metadata_key = f"{self.name}_step_metadata"
            if isinstance(getattr(context, "execution_state", None), dict):
                context.execution_state[step_metadata_key] = {
                    "step_id": step_id,
                    "agent_id": self.name,
                    "start_time": datetime.now(timezone.utc).isoformat(),
                    "execution_count": self.execution_count,
                }
        except Exception:
            pass

        try:
            return await self.run(context)
        except Exception as e:
            # Record failure info, but do NOT complete here (BaseAgent handles it)
            try:
                step_metadata_key = f"{self.name}_step_metadata"
                if isinstance(getattr(context, "execution_state", None),
                              dict) and step_metadata_key in context.execution_state:
                    context.execution_state[step_metadata_key]["end_time"] = datetime.now(timezone.utc).isoformat()
                    context.execution_state[step_metadata_key]["error"] = str(e)
            except Exception:
                pass
            raise

    def _should_retry_exception(self, exception: Exception) -> bool:
        """
        Determine if an exception should be retried based on the agent's retry policy.

        Parameters
        ----------
        exception : Exception
            The exception that occurred during execution

        Returns
        -------
        bool
            True if the exception should be retried, False otherwise
        """
        # Check if it's a OSSS exception with retry policy
        if hasattr(exception, "retry_policy"):
            retry_policy = exception.retry_policy
            return retry_policy in [
                RetryPolicy.IMMEDIATE,
                RetryPolicy.BACKOFF,
                RetryPolicy.CIRCUIT_BREAKER,
            ]

        # Default behavior for non-OSSS exceptions
        # Retry on common transient errors
        if isinstance(exception, (asyncio.TimeoutError, ConnectionError)):
            return True

        # Don't retry on validation, configuration, or authentication errors
        if isinstance(exception, (ValueError, TypeError, AttributeError)):
            return False

        # Default to retry for unknown exceptions (conservative approach)
        return True

    async def _handle_retry_delay(self, retry_attempt: int) -> None:
        """
        Handle delay between retry attempts with exponential backoff and jitter.

        Parameters
        ----------
        retry_attempt : int
            The current retry attempt number (0-based)
        """
        if self.retry_config.base_delay <= 0:
            return

        delay = self.retry_config.base_delay

        if self.retry_config.exponential_backoff:
            delay = min(
                self.retry_config.base_delay * (2**retry_attempt),
                self.retry_config.max_delay,
            )

        if self.retry_config.jitter:
            import random

            # Add ±25% jitter to prevent thundering herd
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
            delay = max(0, delay)  # Ensure non-negative

        self.logger.debug(
            f"[{self.name}] Retrying in {delay:.2f}s (attempt {retry_attempt + 1})"
        )
        await asyncio.sleep(delay)

    def get_execution_stats(self) -> Dict[str, Any]:
        """
        Get execution statistics for this agent.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing execution statistics
        """
        success_rate = (
            (self.success_count / self.execution_count)
            if self.execution_count > 0
            else 0.0
        )

        stats = {
            "agent_name": self.name,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": success_rate,
            "retry_config": {
                "max_retries": self.retry_config.max_retries,
                "base_delay": self.retry_config.base_delay,
                "exponential_backoff": self.retry_config.exponential_backoff,
            },
        }

        if self.circuit_breaker:
            stats["circuit_breaker"] = {
                "is_open": self.circuit_breaker.is_open,
                "failure_count": self.circuit_breaker.failure_count,
                "failure_threshold": self.circuit_breaker.failure_threshold,
            }

        return stats

    def get_node_definition(self) -> LangGraphNodeDefinition:
        """
        Get the LangGraph node definition for this agent.

        This method creates or returns the cached node definition that describes
        this agent as a node in a LangGraph DAG. Subclasses can override
        define_node_metadata() to customize the definition.

        Returns
        -------
        LangGraphNodeDefinition
            Complete node definition including inputs, outputs, and metadata
        """
        if self._node_definition is None:
            self._node_definition = self._create_default_node_definition()
        return self._node_definition

    def _create_default_node_definition(self) -> LangGraphNodeDefinition:
        """Create default node definition for this agent."""
        # Default input/output schemas
        inputs = [
            NodeInputSchema(
                name="context",
                description=f"Agent context containing query and state for {self.name}",
                required=True,
                type_hint="AgentContext",
            )
        ]

        outputs = [
            NodeOutputSchema(
                name="context",
                description=f"Updated context after {self.name} processing",
                type_hint="AgentContext",
            )
        ]

        # Allow subclasses to customize
        node_metadata = self.define_node_metadata()

        return LangGraphNodeDefinition(
            node_id=self.name.lower(),
            node_type=node_metadata.get("node_type", NodeType.PROCESSOR),
            description=node_metadata.get(
                "description", f"{self.name} agent for processing context"
            ),
            inputs=node_metadata.get("inputs", inputs),
            outputs=node_metadata.get("outputs", outputs),
            dependencies=node_metadata.get("dependencies", []),
            tags=node_metadata.get("tags", [self.name.lower(), "agent"]),
        )

    def define_node_metadata(self) -> Dict[str, Any]:
        """
        Define LangGraph node metadata for this agent.

        Subclasses should override this method to provide specific metadata
        for their node type, inputs, outputs, and dependencies.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing node metadata with keys:
            - node_type: NodeType enum value
            - description: Human-readable description
            - inputs: List of NodeInputSchema objects
            - outputs: List of NodeOutputSchema objects
            - dependencies: List of agent names this depends on
            - tags: List of string tags for categorization
        """
        # Default implementation - subclasses can override
        return {}

    def set_node_definition(self, node_definition: LangGraphNodeDefinition) -> None:
        """
        Set a custom node definition for this agent.

        This allows external configuration of the node definition,
        useful for dynamic graph construction.

        Parameters
        ----------
        node_definition : LangGraphNodeDefinition
            Complete node definition to use for this agent
        """
        self._node_definition = node_definition

    def validate_node_compatibility(self, input_context: AgentContext) -> bool:
        """
        Validate that the input context is compatible with this node's requirements.

        This method checks the input context against the node's input schema
        to ensure compatibility before execution.

        Parameters
        ----------
        input_context : AgentContext
            The context to validate

        Returns
        -------
        bool
            True if the context is compatible, False otherwise
        """
        node_def = self.get_node_definition()

        # Basic validation - check that required inputs are present
        for input_schema in node_def.inputs:
            if input_schema.required and input_schema.name == "context":
                # For now, just check that we have a valid AgentContext
                if not isinstance(input_context, AgentContext):
                    return False

        return True

    async def invoke(
        self, state: AgentContext, config: Optional[Dict[str, Any]] = None
    ) -> AgentContext:
        """
        LangGraph-compatible node interface for agent execution.

        This method provides the standard LangGraph node signature while maintaining
        compatibility with our existing agent architecture. It delegates to the
        run_with_retry method to preserve all existing error handling and retry logic.

        Parameters
        ----------
        state : AgentContext
            The current state/context for the graph execution.
        config : Dict[str, Any], optional
            Optional configuration parameters for this invocation.
            Can include step_id, timeout overrides, or other execution parameters.

        Returns
        -------
        AgentContext
            The updated state/context after agent processing.
        """
        # Extract configuration parameters if provided
        step_id = None
        if config:
            step_id = config.get("step_id")

            # Allow config to override timeout for this specific invocation
            original_timeout = self.timeout_seconds
            if "timeout_seconds" in config:
                self.timeout_seconds = config["timeout_seconds"]

            try:
                result = await self.run_with_retry(state, step_id=step_id)
                return result
            finally:
                # Restore original timeout
                self.timeout_seconds = original_timeout
        else:
            # Standard execution without config overrides
            return await self.run_with_retry(state, step_id=step_id)

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentContext:
        """
        Execute the agent asynchronously using the provided context.

        This method should be implemented by concrete agent classes to define
        their specific behavior. The base class handles retry logic, timeouts,
        and error handling around this method.

        Parameters
        ----------
        context : AgentContext
            The context object containing state and input information for the agent.

        Returns
        -------
        AgentContext
            The updated context after agent processing.
        """
        pass  # pragma: no cover