"""
LangGraph node wrappers for OSSS agents.

This module provides wrapper functions that convert OSSS agents
into LangGraph-compatible node functions. Each wrapper handles:
- State conversion between AgentContext and LangGraph state
- Error handling with circuit breaker patterns
- Async execution with proper timeout handling
- Logging and metrics integration
- Output formatting and validation

Design Principles:
- Preserve agent autonomy while enabling DAG execution
- Maintain backward compatibility with existing agents
- Provide robust error handling and recovery
- Enable comprehensive observability and debugging
"""

import asyncio
import time
import inspect

from datetime import datetime, timezone
from typing import (
    Dict,
    Any,
    Optional,
    List,
    Callable,
    Coroutine,
    TypeVar,
    Union,
    cast,
    Protocol,
)
from functools import wraps

from langgraph.runtime import Runtime

from OSSS.ai.context import AgentContext
from OSSS.ai.agents.base_agent import BaseAgent
from OSSS.ai.agents.registry import get_agent_registry
from OSSS.ai.orchestration.state_bridge import AgentContextStateBridge
from OSSS.ai.orchestration.state_schemas import (
    OSSSState,
    OSSSContext,
    RefinerState,
    CriticState,
    HistorianState,
    SynthesisState,
    record_agent_error,
)
from OSSS.ai.observability import get_logger
from OSSS.ai.config.openai_config import OpenAIConfig
from OSSS.ai.llm.openai import OpenAIChatLLM
from OSSS.ai.events import (
    emit_agent_execution_started,
    emit_agent_execution_completed,
)
from OSSS.ai.events.types import EventCategory
from OSSS.ai.utils.content_truncation import truncate_for_websocket_event
from OSSS.ai.orchestration.routing import should_run_historian

logger = get_logger(__name__)

# Global timing registry to store node execution times
_TIMING_REGISTRY: Dict[str, Dict[str, float]] = {}

def _ensure_agent_outputs_nonempty(state: dict, agent_name: str, message: str) -> None:
    exec_state = state.setdefault("execution_state", {})
    if not isinstance(exec_state, dict):
        return
    # Your API seems to rely on this shape existing in execution_state
    aom = exec_state.setdefault("agent_outputs", {})
    if isinstance(aom, dict) and not aom:
        aom[agent_name] = message

async def _coerce_base_agent(agent: Any, agent_name: str) -> BaseAgent:
    """
    Ensure the created object is a BaseAgent instance.
    - Awaits coroutine-returning factories.
    - Raises TypeError if the result is not a BaseAgent.
    """
    if inspect.iscoroutine(agent):
        agent = await agent

    if not isinstance(agent, BaseAgent):
        raise TypeError(
            f"Agent '{agent_name}' constructor returned {type(agent)!r}, expected BaseAgent"
        )

    return agent


def _record_effective_query(state: dict, agent_name: str, effective_query: str) -> None:
    exec_state = state.setdefault("execution_state", {})
    if not isinstance(exec_state, dict):
        return
    eq = exec_state.setdefault("effective_queries", {})
    if isinstance(eq, dict):
        eq[agent_name] = effective_query


def get_timing_registry() -> Dict[str, Dict[str, float]]:
    """Get the current timing registry."""
    return _TIMING_REGISTRY.copy()


def clear_timing_registry() -> None:
    """Clear the timing registry for a new workflow execution."""
    global _TIMING_REGISTRY
    _TIMING_REGISTRY.clear()


def register_node_timing(
    execution_id: str, node_name: str, execution_time_seconds: float
) -> None:
    """Register node execution timing data."""
    global _TIMING_REGISTRY
    if execution_id not in _TIMING_REGISTRY:
        _TIMING_REGISTRY[execution_id] = {}
    _TIMING_REGISTRY[execution_id][node_name] = execution_time_seconds


class NodeExecutionError(Exception):
    """Raised when a node execution fails."""

    pass


F = TypeVar("F", bound=Callable[..., Coroutine[Any, Any, Any]])


class CircuitBreakerFunction(Protocol):
    """Protocol for functions decorated with @circuit_breaker."""

    _failure_count: int
    _circuit_open: bool
    _last_failure_time: Optional[float]

    def __call__(self, *args: Any, **kwargs: Any) -> Coroutine[Any, Any, Any]:
        ...


def circuit_breaker(
    max_failures: int = 3, reset_timeout: float = 300.0
) -> Callable[[F], F]:
    """
    Circuit breaker decorator for node functions.
    """

    def decorator(func: F) -> F:
        circuit_state: Dict[str, Union[int, float, bool, None]] = {
            "failure_count": 0,
            "last_failure_time": None,
            "circuit_open": False,
        }

        def _sync_state() -> None:
            setattr(wrapper, "_failure_count", circuit_state["failure_count"])
            setattr(wrapper, "_last_failure_time", circuit_state["last_failure_time"])
            setattr(wrapper, "_circuit_open", circuit_state["circuit_open"])

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if hasattr(wrapper, "_failure_count"):
                circuit_state["failure_count"] = getattr(wrapper, "_failure_count")
            if hasattr(wrapper, "_last_failure_time"):
                circuit_state["last_failure_time"] = getattr(
                    wrapper, "_last_failure_time"
                )
            if hasattr(wrapper, "_circuit_open"):
                circuit_state["circuit_open"] = getattr(wrapper, "_circuit_open")

            if circuit_state["circuit_open"]:
                if circuit_state["last_failure_time"]:
                    time_since_failure = time.time() - cast(
                        float, circuit_state["last_failure_time"]
                    )
                    if time_since_failure < reset_timeout:
                        raise NodeExecutionError(
                            f"Circuit breaker open for {func.__name__}. "
                            f"Retry in {reset_timeout - time_since_failure:.1f}s"
                        )
                    else:
                        circuit_state["circuit_open"] = False
                        circuit_state["failure_count"] = 0
                        logger.info(f"Circuit breaker reset for {func.__name__}")

            try:
                result = await func(*args, **kwargs)
                circuit_state["failure_count"] = 0
                circuit_state["circuit_open"] = False
                _sync_state()
                return result
            except Exception:
                current_count = cast(int, circuit_state["failure_count"])
                circuit_state["failure_count"] = current_count + 1
                circuit_state["last_failure_time"] = time.time()

                if cast(int, circuit_state["failure_count"]) >= max_failures:
                    circuit_state["circuit_open"] = True
                    logger.error(
                        f"Circuit breaker opened for {func.__name__} "
                        f"after {circuit_state['failure_count']} failures"
                    )

                _sync_state()
                raise

        setattr(wrapper, "_failure_count", 0)
        setattr(wrapper, "_last_failure_time", None)
        setattr(wrapper, "_circuit_open", False)

        return cast(F, wrapper)

    return decorator


def node_metrics(func: F) -> F:
    """
    Decorator to add metrics collection to node functions.
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        node_name = func.__name__.replace("_node", "")

        try:
            logger.info(f"Starting execution of {node_name} node")
            result = await func(*args, **kwargs)

            execution_time_ms = (time.time() - start_time) * 1000
            execution_time_seconds = execution_time_ms / 1000
            logger.info(
                f"Completed {node_name} node execution in {execution_time_ms:.2f}ms"
            )

            context_updated = False

            if hasattr(result, "get") and "final_context" in result:
                final_context = result["final_context"]
                if hasattr(final_context, "execution_state"):
                    if "_node_execution_times" not in final_context.execution_state:
                        final_context.execution_state["_node_execution_times"] = {}
                    final_context.execution_state["_node_execution_times"][
                        node_name
                    ] = execution_time_seconds
                    context_updated = True

            execution_id = None
            if args and isinstance(args[0], dict):
                state = args[0]
                if "execution_metadata" in state:
                    execution_id = state["execution_metadata"].get("execution_id")
                elif "execution_id" in state:
                    execution_id = state["execution_id"]
                else:
                    for _, value in state.items():
                        if isinstance(value, dict) and "execution_id" in value:
                            execution_id = value["execution_id"]
                            break

            if execution_id:
                register_node_timing(execution_id, node_name, execution_time_seconds)
            elif not context_updated:
                logger.debug(
                    f"Could not store timing data for {node_name} node - no execution_id and no context access"
                )

            if isinstance(result, dict):
                if "_node_execution_times" not in result:
                    result["_node_execution_times"] = {}
                result["_node_execution_times"][node_name] = {
                    "execution_time_seconds": execution_time_seconds,
                    "execution_time_ms": execution_time_ms,
                    "completed": True,
                }

            return result

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Failed {node_name} node execution after {execution_time_ms:.2f}ms: {e}"
            )
            raise

    return cast(F, wrapper)


async def create_agent_with_llm(agent_name: str) -> BaseAgent:
    """
    Create an agent instance with LLM configuration and agent-specific settings.
    """
    registry = get_agent_registry()

    llm_config = OpenAIConfig.load()
    llm = OpenAIChatLLM(
        api_key=llm_config.api_key,
        model=llm_config.model,
        base_url=llm_config.base_url,
    )

    agent_config_kwargs: Dict[str, Any] = {}

    # Import agent config classes (optional ones guarded to avoid breaking startup)
    from OSSS.ai.config.agent_configs import (
        HistorianConfig,
        RefinerConfig,
        CriticConfig,
        SynthesisConfig,
    )

    GuardConfig = None
    DataViewConfig = None
    try:
        from OSSS.ai.config.agent_configs import GuardConfig as _GuardConfig  # type: ignore
        GuardConfig = _GuardConfig
    except Exception:
        GuardConfig = None

    try:
        from OSSS.ai.config.agent_configs import DataViewConfig as _DataViewConfig  # type: ignore
        DataViewConfig = _DataViewConfig
    except Exception:
        DataViewConfig = None

    agent_name_lower = agent_name.lower()

    if agent_name_lower == "historian":
        agent_config_kwargs["config"] = HistorianConfig()
    elif agent_name_lower == "refiner":
        agent_config_kwargs["config"] = RefinerConfig()
    elif agent_name_lower == "critic":
        agent_config_kwargs["config"] = CriticConfig()
    elif agent_name_lower == "synthesis":
        agent_config_kwargs["config"] = SynthesisConfig()
    elif agent_name_lower == "guard" and GuardConfig is not None:
        agent_config_kwargs["config"] = GuardConfig()
    elif agent_name_lower == "data_view" and DataViewConfig is not None:
        agent_config_kwargs["config"] = DataViewConfig()

    raw_agent = registry.create_agent(agent_name_lower, llm=llm, **agent_config_kwargs)
    agent = await _coerce_base_agent(raw_agent, agent_name_lower)

    # Apply timeout from configuration after agent creation (optional for guard/data_view)
    if agent_name_lower == "historian":
        agent.timeout_seconds = HistorianConfig().execution_config.timeout_seconds
    elif agent_name_lower == "refiner":
        agent.timeout_seconds = RefinerConfig().execution_config.timeout_seconds
    elif agent_name_lower == "critic":
        agent.timeout_seconds = CriticConfig().execution_config.timeout_seconds
    elif agent_name_lower == "synthesis":
        agent.timeout_seconds = SynthesisConfig().execution_config.timeout_seconds
    elif agent_name_lower == "guard" and GuardConfig is not None:
        agent.timeout_seconds = GuardConfig().execution_config.timeout_seconds
    elif agent_name_lower == "data_view" and DataViewConfig is not None:
        agent.timeout_seconds = DataViewConfig().execution_config.timeout_seconds

    return agent


async def convert_state_to_context(state: OSSSState) -> AgentContext:
    """
    Convert LangGraph state to AgentContext for agent execution.
    """
    bridge = AgentContextStateBridge()

    query = state.get("query", "")
    if "query" not in state:
        raise ValueError("State must contain a query field")

    context = AgentContext(query=query)

    state_exec = state.get("execution_state", {})
    if isinstance(state_exec, dict):
        aom = state_exec.get("agent_output_meta")
        if isinstance(aom, dict):
            context.execution_state["agent_output_meta"] = aom

        eq = state_exec.get("effective_queries")
        if isinstance(eq, dict):
            context.execution_state["effective_queries"] = eq

        rag_ctx = state_exec.get("rag_context")
        if isinstance(rag_ctx, str) and rag_ctx:
            context.execution_state["rag_context"] = rag_ctx

        rag_hits = state_exec.get("rag_hits")
        if isinstance(rag_hits, list):
            context.execution_state["rag_hits"] = rag_hits

        rag_meta = state_exec.get("rag_meta")
        if isinstance(rag_meta, dict):
            context.execution_state["rag_meta"] = rag_meta

        rag_enabled = state_exec.get("rag_enabled")
        if isinstance(rag_enabled, bool):
            context.execution_state["rag_enabled"] = rag_enabled

    so = state.get("structured_outputs")
    if isinstance(so, dict):
        context.execution_state["structured_outputs"] = so

    if state.get("refiner"):
        refiner_state: Optional[RefinerState] = state["refiner"]
        if refiner_state is not None:
            refined_question = refiner_state.get("refined_question", "")
            if refined_question:
                context.add_agent_output("refiner", refined_question)
                context.add_agent_output("Refiner", refined_question)
                context.execution_state["refiner_topics"] = refiner_state.get("topics", [])
                context.execution_state["refiner_confidence"] = refiner_state.get("confidence", 0.8)
                logger.info(f"Added refiner output to context: {str(refined_question)[:100]}...")

    if state.get("critic"):
        critic_state: Optional[CriticState] = state["critic"]
        if critic_state is not None:
            critique = critic_state.get("critique", "")
            if critique:
                context.add_agent_output("critic", critique)
                context.add_agent_output("Critic", critique)
                context.execution_state["critic_suggestions"] = critic_state.get("suggestions", [])
                context.execution_state["critic_severity"] = critic_state.get("severity", "medium")
                logger.info(f"Added critic output to context: {str(critique)[:100]}...")

    if state.get("historian"):
        historian_state: Optional[HistorianState] = state["historian"]
        if historian_state is not None:
            historical_summary = historian_state.get("historical_summary", "")
            if historical_summary:
                context.add_agent_output("historian", historical_summary)
                context.add_agent_output("Historian", historical_summary)
                context.execution_state["historian_retrieved_notes"] = historian_state.get("retrieved_notes", [])
                context.execution_state["historian_search_strategy"] = historian_state.get("search_strategy", "hybrid")
                context.execution_state["historian_topics_found"] = historian_state.get("topics_found", [])
                context.execution_state["historian_confidence"] = historian_state.get("confidence", 0.8)
                logger.info(f"Added historian output to context: {str(historical_summary)[:100]}...")

    if state.get("synthesis"):
        # Not required, but handy if your DataView agent wants the final analysis in context
        syn = state.get("synthesis")
        if isinstance(syn, dict):
            final_analysis = syn.get("final_analysis", "")
            if isinstance(final_analysis, str) and final_analysis:
                context.add_agent_output("synthesis", final_analysis)
                context.add_agent_output("Synthesis", final_analysis)

    execution_metadata = state.get("execution_metadata", {})
    if isinstance(execution_metadata, dict) and execution_metadata:
        context.execution_state.update(
            {
                "execution_id": execution_metadata.get("execution_id", ""),
                "orchestrator_type": "langgraph-real",
                "successful_agents": (
                    state.get("successful_agents", []).copy()
                    if isinstance(state.get("successful_agents"), list)
                    else []
                ),
                "failed_agents": (
                    state.get("failed_agents", []).copy()
                    if isinstance(state.get("failed_agents"), list)
                    else []
                ),
            }
        )

    return context


# ---------------------------------------------------------------------
# ✅ NEW: guard_node
# ---------------------------------------------------------------------
@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def guard_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    thread_id = runtime.context.thread_id
    execution_id = runtime.context.execution_id
    original_query = runtime.context.query or state.get("query", "")
    correlation_id = runtime.context.correlation_id
    checkpoint_enabled = runtime.context.enable_checkpoints

    logger.info(
        f"Executing guard node in thread {thread_id}",
        extra={
            "thread_id": thread_id,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
            "checkpoint_enabled": checkpoint_enabled,
        },
    )

    exec_state = state.get("execution_state", {})
    if not isinstance(exec_state, dict):
        exec_state = {}

    # record effective query
    _record_effective_query(state, "guard", original_query)

    try:
        emit_agent_execution_started(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name="guard",
            input_context={"query": original_query, "thread_id": thread_id, "execution_id": execution_id},
            correlation_id=correlation_id,
            metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
        )

        # Try to create a real agent if it exists
        try:
            agent = await create_agent_with_llm("guard")
        except Exception as e:
            # ✅ No-op but MUST still output something
            msg = f"Guard not configured; passed through query unchanged. ({type(e).__name__})"
            logger.warning(f"Guard agent not available; guard_node is a no-op: {e}")

            exec_state["guard"] = {
                "allowed": True,
                "action": "noop",
                "reason": "agent_unavailable",
                "message": msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # ✅ Ensure downstream WorkflowResponse does not see empty outputs
            _ensure_agent_outputs_nonempty(state, "guard", msg)

            emit_agent_execution_completed(
                event_category=EventCategory.EXECUTION,
                workflow_id=execution_id,
                agent_name="guard",
                success=True,
                output_context={"allowed": True, "action": "noop", "thread_id": thread_id, "execution_id": execution_id},
                correlation_id=correlation_id,
                metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
            )

            return {
                "execution_state": exec_state,
                "successful_agents": ["guard"],
                # keep structured outputs if you use them elsewhere
                "structured_outputs": state.get("structured_outputs", {}) or {},
            }

        # If you DO have a real guard agent, run it
        context = await convert_state_to_context(state)
        result_context = await agent.run_with_retry(context)

        guard_output = result_context.agent_outputs.get("guard", "") or "Guard completed."
        exec_state["guard"] = result_context.execution_state.get("guard", {"message": guard_output})

        # ✅ Ensure non-empty output
        _ensure_agent_outputs_nonempty(state, "guard", guard_output)

        emit_agent_execution_completed(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name="guard",
            success=True,
            output_context={"message": truncate_for_websocket_event(guard_output, "guard"), "thread_id": thread_id},
            correlation_id=correlation_id,
            metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
        )

        return {
            "execution_state": exec_state,
            "successful_agents": ["guard"],
            "structured_outputs": result_context.execution_state.get("structured_outputs", {}) or {},
        }

    except Exception as e:
        emit_agent_execution_completed(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name="guard",
            success=False,
            output_context={"error": str(e), "thread_id": thread_id},
            error_message=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
            metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
        )
        record_agent_error(state, "guard", e)
        raise NodeExecutionError(f"Guard execution failed: {e}") from e


# ---------------------------------------------------------------------
# ✅ NEW: data_view_node
# ---------------------------------------------------------------------
@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def data_view_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    """
    LangGraph node wrapper for DataViewAgent.

    Intended to transform outputs into structured/table-friendly payloads.
    If the agent is not registered, degrades gracefully (no-op).
    """
    thread_id = runtime.context.thread_id
    execution_id = runtime.context.execution_id
    original_query = runtime.context.query
    correlation_id = runtime.context.correlation_id
    checkpoint_enabled = runtime.context.enable_checkpoints

    logger.info(
        f"Executing data_view node in thread {thread_id}",
        extra={
            "thread_id": thread_id,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
            "checkpoint_enabled": checkpoint_enabled,
        },
    )

    workflow_id = execution_id

    try:
        # Usually you want synthesis completed before you produce a view.
        if not state.get("synthesis"):
            raise NodeExecutionError("data_view node requires synthesis output")

        emit_agent_execution_started(
            event_category=EventCategory.EXECUTION,
            workflow_id=workflow_id,
            agent_name="data_view",
            input_context={
                "query": original_query or state.get("query", ""),
                "node_type": "data_view",
                "thread_id": thread_id,
                "execution_id": execution_id,
            },
            correlation_id=correlation_id,
            metadata={
                "node_execution": True,
                "orchestrator_type": "langgraph-real",
                "runtime_context": {
                    "thread_id": thread_id,
                    "execution_id": execution_id,
                    "checkpoint_enabled": checkpoint_enabled,
                },
            },
        )

        try:
            agent = await create_agent_with_llm("data_view")
        except Exception as e:
            logger.warning(f"DataView agent not available; data_view_node is a no-op: {e}")
            exec_state = state.get("execution_state", {})
            if not isinstance(exec_state, dict):
                exec_state = {}
            exec_state["data_view"] = {"status": "skipped", "reason": "agent_not_registered"}
            return {
                "execution_state": exec_state,
                "data_view": exec_state["data_view"],
                "successful_agents": [],
                "structured_outputs": state.get("structured_outputs", {}) or {},
            }

        context = await convert_state_to_context(state)

        refined = ""
        try:
            if state.get("refiner"):
                refined = cast(RefinerState, state["refiner"]).get("refined_question", "")  # type: ignore[arg-type]
        except Exception:
            refined = ""

        effective_query = refined or (original_query or state.get("query", "") or context.query)
        _record_effective_query(state, "data_view", effective_query)

        result_context = await agent.run_with_retry(context)
        data_view_raw_output = result_context.agent_outputs.get("data_view", "")

        # Prefer structured payload produced by the agent; otherwise fall back to raw
        view_payload = result_context.execution_state.get("data_view_payload")
        if view_payload is None:
            view_payload = result_context.execution_state.get("structured_outputs")

        data_view_state: Dict[str, Any] = {
            "payload": view_payload,
            "raw": truncate_for_websocket_event(str(data_view_raw_output), "data_view"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        token_usage = result_context.get_agent_token_usage("data_view")

        emit_agent_execution_completed(
            event_category=EventCategory.EXECUTION,
            workflow_id=workflow_id,
            agent_name="data_view",
            success=True,
            output_context={
                "node_type": "data_view",
                "thread_id": thread_id,
                "execution_id": execution_id,
                "has_payload": bool(view_payload),
                "input_tokens": token_usage["input_tokens"],
                "output_tokens": token_usage["output_tokens"],
                "total_tokens": token_usage["total_tokens"],
            },
            correlation_id=correlation_id,
            metadata={
                "node_execution": True,
                "orchestrator_type": "langgraph-real",
                "token_usage": token_usage,
            },
        )

        structured_outputs = result_context.execution_state.get("structured_outputs", {})
        exec_state = state.get("execution_state", {})
        if not isinstance(exec_state, dict):
            exec_state = {}
        exec_state["data_view"] = data_view_state

        return {
            "execution_state": exec_state,
            "data_view": data_view_state,
            "successful_agents": ["data_view"],
            "structured_outputs": structured_outputs,
        }

    except Exception as e:
        logger.error(f"data_view node failed: {e}")
        emit_agent_execution_completed(
            event_category=EventCategory.EXECUTION,
            workflow_id=workflow_id,
            agent_name="data_view",
            success=False,
            output_context={
                "error": str(e),
                "node_type": "data_view",
                "thread_id": thread_id,
                "execution_id": execution_id,
            },
            error_message=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
            metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
        )
        record_agent_error(state, "data_view", e)
        raise NodeExecutionError(f"DataView execution failed: {e}") from e


# ---------------------------------------------------------------------
# Existing nodes (unchanged): refiner_node, critic_node, historian_node, synthesis_node
# ---------------------------------------------------------------------

@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def refiner_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    # (UNCHANGED FROM YOUR VERSION)
    thread_id = runtime.context.thread_id
    execution_id = runtime.context.execution_id
    original_query = runtime.context.query
    correlation_id = runtime.context.correlation_id
    checkpoint_enabled = runtime.context.enable_checkpoints

    logger.info(
        f"Executing refiner node in thread {thread_id}",
        extra={
            "thread_id": thread_id,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
            "query_length": len(original_query or ""),
            "checkpoint_enabled": checkpoint_enabled,
        },
    )

    workflow_id = execution_id

    try:
        emit_agent_execution_started(
            event_category=EventCategory.EXECUTION,
            workflow_id=workflow_id,
            agent_name="refiner",
            input_context={
                "query": original_query or state.get("query", ""),
                "node_type": "refiner",
                "thread_id": thread_id,
                "execution_id": execution_id,
            },
            correlation_id=correlation_id,
            metadata={
                "node_execution": True,
                "orchestrator_type": "langgraph-real",
                "runtime_context": {
                    "thread_id": thread_id,
                    "execution_id": execution_id,
                    "checkpoint_enabled": checkpoint_enabled,
                    "query_length": len(original_query or ""),
                },
            },
        )

        agent = await create_agent_with_llm("refiner")
        context = await convert_state_to_context(state)

        effective_query = original_query or state.get("query", "") or context.query
        _record_effective_query(state, "refiner", effective_query)

        result_context = await agent.run_with_retry(context)
        refiner_raw_output = result_context.agent_outputs.get("refiner", "")

        refiner_state = RefinerState(
            refined_question=refiner_raw_output,
            topics=result_context.execution_state.get("topics", []),
            confidence=result_context.execution_state.get("confidence", 0.8),
            processing_notes=result_context.execution_state.get("processing_notes"),
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_output_meta=context.execution_state.get("agent_output_meta", {}),
        )

        refiner_token_usage = result_context.get_agent_token_usage("refiner")

        emit_agent_execution_completed(
            event_category=EventCategory.EXECUTION,
            workflow_id=workflow_id,
            agent_name="refiner",
            success=True,
            output_context={
                "refined_question": truncate_for_websocket_event(
                    str(refiner_raw_output), "refined_question"
                ),
                "node_type": "refiner",
                "thread_id": thread_id,
                "execution_id": execution_id,
                "confidence": refiner_state["confidence"],
                "topics_count": len(refiner_state["topics"]),
                "input_tokens": refiner_token_usage["input_tokens"],
                "output_tokens": refiner_token_usage["output_tokens"],
                "total_tokens": refiner_token_usage["total_tokens"],
            },
            correlation_id=correlation_id,
            metadata={
                "node_execution": True,
                "orchestrator_type": "langgraph-real",
                "token_usage": refiner_token_usage,
            },
        )

        structured_outputs = result_context.execution_state.get("structured_outputs", {})
        exec_state = state.get("execution_state", {})
        if not isinstance(exec_state, dict):
            exec_state = {}

        return {
            "execution_state": exec_state,
            "refiner": refiner_state,
            "successful_agents": ["refiner"],
            "structured_outputs": structured_outputs,
        }

    except Exception as e:
        logger.error(
            f"Refiner node failed for thread {thread_id}: {e}",
            extra={
                "thread_id": thread_id,
                "execution_id": execution_id,
                "correlation_id": correlation_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "checkpoint_enabled": checkpoint_enabled,
                "query_length": len(original_query or ""),
            },
        )

        emit_agent_execution_completed(
            event_category=EventCategory.EXECUTION,
            workflow_id=workflow_id,
            agent_name="refiner",
            success=False,
            output_context={
                "error": str(e),
                "node_type": "refiner",
                "thread_id": thread_id,
                "execution_id": execution_id,
            },
            error_message=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
            metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
        )

        record_agent_error(state, "refiner", e)
        raise NodeExecutionError(f"Refiner execution failed: {e}") from e


@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def critic_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    # (UNCHANGED FROM YOUR VERSION)
    thread_id = runtime.context.thread_id
    execution_id = runtime.context.execution_id
    original_query = runtime.context.query
    correlation_id = runtime.context.correlation_id
    checkpoint_enabled = runtime.context.enable_checkpoints

    logger.info(
        f"Executing critic node in thread {thread_id}",
        extra={
            "thread_id": thread_id,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
            "query_length": len(original_query or ""),
            "checkpoint_enabled": checkpoint_enabled,
        },
    )

    try:
        if not state.get("refiner"):
            raise NodeExecutionError("Critic node requires refiner output")

        emit_agent_execution_started(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name="critic",
            input_context={
                "query": original_query or "",
                "has_refiner_output": True,
                "node_type": "critic",
                "thread_id": thread_id,
                "runtime_context": True,
            },
            correlation_id=correlation_id,
            metadata={
                "node_execution": True,
                "orchestrator_type": "langgraph-real",
                "runtime_api_version": "0.6.4",
                "thread_id": thread_id,
                "checkpoint_enabled": checkpoint_enabled,
            },
        )

        agent = await create_agent_with_llm("critic")
        context = await convert_state_to_context(state)

        refined = ""
        try:
            if state.get("refiner"):
                refined = cast(RefinerState, state["refiner"]).get("refined_question", "")  # type: ignore[arg-type]
        except Exception:
            refined = ""

        effective_query = refined or (original_query or state.get("query", "") or context.query)
        _record_effective_query(state, "critic", effective_query)

        result_context = await agent.run_with_retry(context)
        critic_raw_output = result_context.agent_outputs.get("critic", "")

        critic_state = CriticState(
            critique=critic_raw_output,
            suggestions=result_context.execution_state.get("suggestions", []),
            severity=result_context.execution_state.get("severity", "medium"),
            strengths=result_context.execution_state.get("strengths", []),
            weaknesses=result_context.execution_state.get("weaknesses", []),
            confidence=result_context.execution_state.get("confidence", 0.7),
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_output_meta=context.execution_state.get("agent_output_meta", {}),
        )

        critic_token_usage = result_context.get_agent_token_usage("critic")

        emit_agent_execution_completed(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name="critic",
            success=True,
            output_context={
                "critique": truncate_for_websocket_event(str(critic_raw_output), "critique"),
                "node_type": "critic",
                "thread_id": thread_id,
                "runtime_context": True,
                "confidence": critic_state["confidence"],
                "input_tokens": critic_token_usage["input_tokens"],
                "output_tokens": critic_token_usage["output_tokens"],
                "total_tokens": critic_token_usage["total_tokens"],
            },
            correlation_id=correlation_id,
            metadata={
                "node_execution": True,
                "orchestrator_type": "langgraph-real",
                "runtime_api_version": "0.6.4",
                "thread_id": thread_id,
                "checkpoint_enabled": checkpoint_enabled,
            },
        )

        structured_outputs = result_context.execution_state.get("structured_outputs", {})
        exec_state = state.get("execution_state", {})
        if not isinstance(exec_state, dict):
            exec_state = {}

        return {
            "execution_state": exec_state,
            "critic": critic_state,
            "successful_agents": ["critic"],
            "structured_outputs": structured_outputs,
        }

    except Exception as e:
        logger.error(f"Critic node failed: {e}")
        emit_agent_execution_completed(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name="critic",
            success=False,
            output_context={
                "error": str(e),
                "node_type": "critic",
                "thread_id": thread_id,
                "runtime_context": True,
            },
            error_message=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
            metadata={
                "node_execution": True,
                "orchestrator_type": "langgraph-real",
                "runtime_api_version": "0.6.4",
                "thread_id": thread_id,
                "checkpoint_enabled": checkpoint_enabled,
            },
        )
        record_agent_error(state, "critic", e)
        raise NodeExecutionError(f"Critic execution failed: {e}") from e


@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def historian_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    # (UNCHANGED FROM YOUR VERSION, plus your skip behavior)
    thread_id = runtime.context.thread_id
    execution_id = runtime.context.execution_id
    original_query = runtime.context.query
    correlation_id = runtime.context.correlation_id
    checkpoint_enabled = runtime.context.enable_checkpoints

    logger.info(
        f"Executing historian node in thread {thread_id}",
        extra={
            "thread_id": thread_id,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
            "query_length": len(original_query or ""),
            "checkpoint_enabled": checkpoint_enabled,
        },
    )

    if not should_run_historian(original_query or ""):
        logger.info("Skipping historian node (routing heuristic)")

        refined = ""
        try:
            if state.get("refiner"):
                refined = cast(RefinerState, state["refiner"]).get("refined_question", "")  # type: ignore[arg-type]
        except Exception:
            refined = ""
        effective_query = refined or (original_query or state.get("query", ""))
        _record_effective_query(state, "historian", effective_query)

        exec_state = state.get("execution_state", {})
        if not isinstance(exec_state, dict):
            exec_state = {}

        return {
            "execution_state": exec_state,
            "historian": None,
            "successful_agents": [],
            "structured_outputs": state.get("structured_outputs", {}) or {},
        }

    try:
        if not state.get("refiner"):
            raise NodeExecutionError("Historian node requires refiner output")

        emit_agent_execution_started(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name="historian",
            input_context={
                "query": original_query or "",
                "has_refiner_output": True,
                "node_type": "historian",
                "thread_id": thread_id,
                "runtime_context": True,
            },
            correlation_id=correlation_id,
            metadata={
                "node_execution": True,
                "orchestrator_type": "langgraph-real",
                "runtime_api_version": "0.6.4",
                "thread_id": thread_id,
                "checkpoint_enabled": checkpoint_enabled,
            },
        )

        agent = await create_agent_with_llm("historian")
        context = await convert_state_to_context(state)

        refined = ""
        try:
            if state.get("refiner"):
                refined = cast(RefinerState, state["refiner"]).get("refined_question", "")  # type: ignore[arg-type]
        except Exception:
            refined = ""

        effective_query = refined or (original_query or state.get("query", "") or context.query)
        _record_effective_query(state, "historian", effective_query)

        result_context = await agent.run_with_retry(context)
        historian_raw_output = result_context.agent_outputs.get("historian", "")

        retrieved_notes = getattr(result_context, "retrieved_notes", [])
        topics_found = []
        if hasattr(result_context, "execution_state"):
            topics_found = result_context.execution_state.get("topics_found", [])

        historian_state = HistorianState(
            historical_summary=historian_raw_output,
            retrieved_notes=retrieved_notes,
            search_results_count=result_context.execution_state.get("search_results_count", 0),
            filtered_results_count=result_context.execution_state.get("filtered_results_count", 0),
            search_strategy=result_context.execution_state.get("search_strategy", "hybrid"),
            topics_found=topics_found,
            confidence=result_context.execution_state.get("confidence", 0.8),
            llm_analysis_used=result_context.execution_state.get("llm_analysis_used", True),
            metadata=result_context.execution_state.get("historian_metadata", {}),
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_output_meta=context.execution_state.get("agent_output_meta", {}),
        )

        historian_token_usage = result_context.get_agent_token_usage("historian")

        emit_agent_execution_completed(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name="historian",
            success=True,
            output_context={
                "historical_summary": truncate_for_websocket_event(str(historian_raw_output), "historical_summary"),
                "node_type": "historian",
                "thread_id": thread_id,
                "runtime_context": True,
                "confidence": historian_state["confidence"],
                "search_strategy": historian_state["search_strategy"],
                "input_tokens": historian_token_usage["input_tokens"],
                "output_tokens": historian_token_usage["output_tokens"],
                "total_tokens": historian_token_usage["total_tokens"],
            },
            correlation_id=correlation_id,
            metadata={
                "node_execution": True,
                "orchestrator_type": "langgraph-real",
                "runtime_api_version": "0.6.4",
                "thread_id": thread_id,
                "checkpoint_enabled": checkpoint_enabled,
            },
        )

        structured_outputs = result_context.execution_state.get("structured_outputs", {})
        exec_state = state.get("execution_state", {})
        if not isinstance(exec_state, dict):
            exec_state = {}

        return {
            "execution_state": exec_state,
            "historian": historian_state,
            "successful_agents": ["historian"],
            "structured_outputs": structured_outputs,
        }

    except Exception as e:
        logger.error(f"Historian node failed: {e}")
        emit_agent_execution_completed(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name="historian",
            success=False,
            output_context={
                "error": str(e),
                "node_type": "historian",
                "thread_id": thread_id,
                "runtime_context": True,
            },
            error_message=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
            metadata={
                "node_execution": True,
                "orchestrator_type": "langgraph-real",
                "runtime_api_version": "0.6.4",
                "thread_id": thread_id,
                "checkpoint_enabled": checkpoint_enabled,
            },
        )
        record_agent_error(state, "historian", e)
        raise NodeExecutionError(f"Historian execution failed: {e}") from e


@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def synthesis_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    # (UNCHANGED FROM YOUR VERSION)
    thread_id = runtime.context.thread_id
    execution_id = runtime.context.execution_id
    original_query = runtime.context.query
    correlation_id = runtime.context.correlation_id
    checkpoint_enabled = runtime.context.enable_checkpoints

    logger.info(
        f"Executing synthesis node in thread {thread_id}",
        extra={
            "thread_id": thread_id,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
            "query_length": len(original_query or ""),
            "checkpoint_enabled": checkpoint_enabled,
        },
    )

    try:
        if not state.get("refiner"):
            raise NodeExecutionError("Synthesis node requires refiner output")
        if not state.get("critic"):
            raise NodeExecutionError("Synthesis node requires critic output")
        if not state.get("historian"):
            if should_run_historian(original_query or ""):
                raise NodeExecutionError("Synthesis node requires historian output for this query")
            logger.info("Proceeding without historian output (skipped by routing)")

        emit_agent_execution_started(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name="synthesis",
            input_context={
                "query": original_query or "",
                "has_all_inputs": True,
                "node_type": "synthesis",
                "thread_id": thread_id,
                "runtime_context": True,
            },
            correlation_id=correlation_id,
            metadata={
                "node_execution": True,
                "orchestrator_type": "langgraph-real",
                "runtime_api_version": "0.6.4",
                "thread_id": thread_id,
                "checkpoint_enabled": checkpoint_enabled,
            },
        )

        agent = await create_agent_with_llm("synthesis")
        context = await convert_state_to_context(state)

        refined = ""
        try:
            if state.get("refiner"):
                refined = cast(RefinerState, state["refiner"]).get("refined_question", "")  # type: ignore[arg-type]
        except Exception:
            refined = ""

        effective_query = refined or (original_query or state.get("query", "") or context.query)
        _record_effective_query(state, "synthesis", effective_query)

        result_context = await agent.run_with_retry(context)
        synthesis_raw_output = result_context.agent_outputs.get("synthesis", "")

        sources_used = []
        if state.get("refiner"):
            sources_used.append("refiner")
        if state.get("critic"):
            sources_used.append("critic")
        if state.get("historian"):
            sources_used.append("historian")

        synthesis_state = SynthesisState(
            final_analysis=synthesis_raw_output,
            key_insights=result_context.execution_state.get("key_insights", []),
            sources_used=sources_used,
            themes_identified=result_context.execution_state.get("themes", []),
            conflicts_resolved=result_context.execution_state.get("conflicts_resolved", 0),
            confidence=result_context.execution_state.get("confidence", 0.8),
            metadata=result_context.execution_state.get("synthesis_metadata", {}),
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_output_meta=context.execution_state.get("agent_output_meta", {}),
        )

        synthesis_token_usage = result_context.get_agent_token_usage("synthesis")

        emit_agent_execution_completed(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name="synthesis",
            success=True,
            output_context={
                "final_analysis": truncate_for_websocket_event(str(synthesis_raw_output), "final_analysis"),
                "node_type": "synthesis",
                "thread_id": thread_id,
                "runtime_context": True,
                "confidence": synthesis_state["confidence"],
                "sources_used": synthesis_state["sources_used"],
                "input_tokens": synthesis_token_usage["input_tokens"],
                "output_tokens": synthesis_token_usage["output_tokens"],
                "total_tokens": synthesis_token_usage["total_tokens"],
            },
            correlation_id=correlation_id,
            metadata={
                "node_execution": True,
                "orchestrator_type": "langgraph-real",
                "runtime_api_version": "0.6.4",
                "thread_id": thread_id,
                "checkpoint_enabled": checkpoint_enabled,
            },
        )

        structured_outputs = result_context.execution_state.get("structured_outputs", {})
        exec_state = state.get("execution_state", {})
        if not isinstance(exec_state, dict):
            exec_state = {}

        return {
            "execution_state": exec_state,
            "synthesis": synthesis_state,
            "successful_agents": ["synthesis"],
            "structured_outputs": structured_outputs,
        }

    except Exception as e:
        logger.error(f"Synthesis node failed: {e}")
        emit_agent_execution_completed(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name="synthesis",
            success=False,
            output_context={
                "error": str(e),
                "node_type": "synthesis",
                "thread_id": thread_id,
                "runtime_context": True,
            },
            error_message=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
            metadata={
                "node_execution": True,
                "orchestrator_type": "langgraph-real",
                "runtime_api_version": "0.6.4",
                "thread_id": thread_id,
                "checkpoint_enabled": checkpoint_enabled,
            },
        )
        record_agent_error(state, "synthesis", e)
        raise NodeExecutionError(f"Synthesis execution failed: {e}") from e


async def handle_node_timeout(
    coro: Coroutine[Any, Any, Any], timeout_seconds: float = 30.0
) -> Any:
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise NodeExecutionError(f"Node execution timed out after {timeout_seconds}s")


def get_node_dependencies() -> Dict[str, List[str]]:
    return {
        "guard": [],
        "refiner": [],
        "critic": ["refiner"],
        "historian": ["refiner"],
        "synthesis": ["critic"],  # historian optional
        "data_view": ["synthesis"],
    }


def validate_node_input(state: OSSSState, node_name: str) -> bool:
    dependencies = get_node_dependencies()
    required_deps = dependencies.get(node_name, [])

    missing_deps = []
    for dep in required_deps:
        if not state.get(dep):
            missing_deps.append(dep)
            logger.warning(f"Node {node_name} missing required dependency: {dep}")

    return len(missing_deps) == 0


__all__ = [
    "guard_node",
    "refiner_node",
    "critic_node",
    "historian_node",
    "synthesis_node",
    "data_view_node",
    "NodeExecutionError",
    "circuit_breaker",
    "node_metrics",
    "handle_node_timeout",
    "get_node_dependencies",
    "validate_node_input",
    "create_agent_with_llm",
    "convert_state_to_context",
    "CircuitBreakerFunction",
]
