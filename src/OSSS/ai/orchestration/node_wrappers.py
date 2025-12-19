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


# ---------------------------------------------------------------------
# Small internal helpers
# ---------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_exec_state_dict(state: OSSSState) -> Dict[str, Any]:
    """
    Ensure state["execution_state"] exists and is a dict.
    Returns the dict.
    """
    exec_state = state.setdefault("execution_state", {})
    if not isinstance(exec_state, dict):
        exec_state = {}
        state["execution_state"] = exec_state
    return exec_state


def _first_present(state: OSSSState, *keys: str) -> Optional[Any]:
    """
    Return the first non-None value found for the given keys.
    (Does not treat empty dict/empty string specially; adjust if you want.)
    """
    for k in keys:
        v = state.get(k)
        if v is not None:
            return v
    return None


# ---------------------------------------------------------------------
# Legacy execution_state helpers (keep for backwards compatibility)
# ---------------------------------------------------------------------
def _ensure_agent_outputs_nonempty(state: dict, agent_name: str, message: str) -> None:
    exec_state = state.setdefault("execution_state", {})
    if not isinstance(exec_state, dict):
        return
    aom = exec_state.setdefault("agent_outputs", {})
    if isinstance(aom, dict) and not aom:
        aom[agent_name] = message


def _set_agent_output(state: dict, agent_name: str, output: Any) -> None:
    """
    Store agent output in the legacy shape your API expects.
    """
    exec_state = state.setdefault("execution_state", {})
    if not isinstance(exec_state, dict):
        return
    aom = exec_state.setdefault("agent_outputs", {})
    if isinstance(aom, dict):
        aom[agent_name] = output


def _record_effective_query(state: dict, agent_name: str, effective_query: str) -> None:
    exec_state = state.setdefault("execution_state", {})
    if not isinstance(exec_state, dict):
        return
    eq = exec_state.setdefault("effective_queries", {})
    if isinstance(eq, dict):
        eq[agent_name] = effective_query


# ---------------------------------------------------------------------
# Canonical state helpers (typed OSSSState fields)
# ---------------------------------------------------------------------
def _merge_structured_outputs(state: OSSSState, patch: Dict[str, Any]) -> None:
    so = state.get("structured_outputs")
    if not isinstance(so, dict):
        state["structured_outputs"] = {}
        so = state["structured_outputs"]
    so.update(patch)


def _set_guard_decision(state: dict, decision: str) -> None:
    """
    Normalized routing key for the guard pipeline graph.
    Expected by GraphFactory.route_after_guard().
    """
    d = (decision or "").strip().lower()
    if d not in {"allow", "requires_confirmation", "block"}:
        d = "block"
    state["guard_decision"] = d


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
    elif agent_name_lower == "data_views" and DataViewConfig is not None:
        agent_config_kwargs["config"] = DataViewConfig()

    raw_agent = registry.create_agent(agent_name_lower, llm=llm, **agent_config_kwargs)
    agent = await _coerce_base_agent(raw_agent, agent_name_lower)

    # Keep existing per-agent timeouts (no behavior change)
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
    elif agent_name_lower == "data_views" and DataViewConfig is not None:
        agent.timeout_seconds = DataViewConfig().execution_config.timeout_seconds

    return agent


async def convert_state_to_context(state: OSSSState) -> AgentContext:
    """
    Convert LangGraph state to AgentContext for agent execution.
    """
    _ = AgentContextStateBridge()  # kept for compatibility / future use

    query = state.get("query", "")
    if "query" not in state:
        raise ValueError("State must contain a query field")

    context = AgentContext(query=query)

    # Legacy passthrough to AgentContext.execution_state (optional)
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

    if state.get("critic"):
        critic_state: Optional[CriticState] = state["critic"]
        if critic_state is not None:
            critique = critic_state.get("critique", "")
            if critique:
                context.add_agent_output("critic", critique)
                context.add_agent_output("Critic", critique)
                context.execution_state["critic_suggestions"] = critic_state.get("suggestions", [])
                context.execution_state["critic_severity"] = critic_state.get("severity", "medium")

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

    if state.get("synthesis"):
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



# ---------------------------------------------------------------------
# ✅ Guard pipeline nodes
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

    exec_state = _ensure_exec_state_dict(state)
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

        try:
            agent = await create_agent_with_llm("guard")
        except Exception as e:
            msg = f"Guard not configured; passed through query unchanged. ({type(e).__name__})"
            logger.warning(f"Guard agent not available; guard_node is a no-op: {e}")

            guard_payload: Dict[str, Any] = {
                "allowed": True,
                "decision": "allow",
                "action": "noop",
                "reason": "agent_unavailable",
                "message": msg,
                "timestamp": _now_iso(),
            }

            exec_state["guard"] = guard_payload
            state["guard"] = guard_payload
            _set_guard_decision(state, "allow")
            _merge_structured_outputs(state, {"guard": guard_payload})

            _set_agent_output(state, "guard", guard_payload)
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
                "guard": guard_payload,
                "guard_decision": state.get("guard_decision"),
                "successful_agents": ["guard"],
                "structured_outputs": state.get("structured_outputs", {}) or {},
            }

        context = await convert_state_to_context(state)
        result_context = await agent.run_with_retry(context)

        guard_output = result_context.agent_outputs.get("guard", "") or "Guard completed."
        raw_payload = result_context.execution_state.get("guard")
        if not isinstance(raw_payload, dict):
            raw_payload = {"message": guard_output}

        decision = (
            result_context.execution_state.get("guard_decision")
            or raw_payload.get("decision")
            or raw_payload.get("guard_decision")
            or ""
        )

        if not decision:
            allowed = raw_payload.get("allowed")
            decision = "allow" if allowed is not False else "block"

        guard_payload = {
            "allowed": bool(raw_payload.get("allowed", True)),
            "decision": str(decision),
            "action": str(raw_payload.get("action", "guard")),
            "reason": str(raw_payload.get("reason", "")),
            "message": str(raw_payload.get("message", guard_output)),
            "timestamp": _now_iso(),
        }

        exec_state["guard"] = guard_payload
        state["guard"] = guard_payload
        _set_guard_decision(state, decision)
        _merge_structured_outputs(state, {"guard": guard_payload})

        _set_agent_output(state, "guard", guard_payload)
        _ensure_agent_outputs_nonempty(state, "guard", guard_payload["message"] or guard_output)

        emit_agent_execution_completed(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name="guard",
            success=True,
            output_context={"message": truncate_for_websocket_event(guard_payload["message"], "guard"), "thread_id": thread_id},
            correlation_id=correlation_id,
            metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
        )

        return {
            "execution_state": exec_state,
            "guard": guard_payload,
            "guard_decision": state.get("guard_decision"),
            "successful_agents": ["guard"],
            "structured_outputs": state.get("structured_outputs", {}) or {},
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


@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def answer_search_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    """
    Executes the "answer/search" step after guard allows the request.
    Tries to run a registered agent named 'answer_search'. If not registered,
    degrades gracefully by using synthesis output (or the query) as a stub answer.
    """
    thread_id = runtime.context.thread_id
    execution_id = runtime.context.execution_id
    original_query = runtime.context.query or state.get("query", "")
    correlation_id = runtime.context.correlation_id

    logger.info(
        f"Executing answer_search node in thread {thread_id}",
        extra={"thread_id": thread_id, "execution_id": execution_id, "correlation_id": correlation_id},
    )

    exec_state = _ensure_exec_state_dict(state)
    _record_effective_query(state, "answer_search", original_query)

    try:
        emit_agent_execution_started(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name="answer_search",
            input_context={"query": original_query, "thread_id": thread_id, "execution_id": execution_id},
            correlation_id=correlation_id,
            metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
        )

        try:
            agent = await create_agent_with_llm("answer_search")
        except Exception as e:
            logger.warning(f"answer_search agent not available; falling back: {e}")

            syn = state.get("synthesis") or {}
            fallback_answer = ""
            if isinstance(syn, dict):
                fallback_answer = syn.get("final_analysis", "") or ""
            if not fallback_answer:
                fallback_answer = f"(stub) Answer/search for: {original_query}"

            payload: Dict[str, Any] = {
                "ok": True,
                "type": "answer_search",
                "answer_text": fallback_answer,
                "sources": [],
                "timestamp": _now_iso(),
                "fallback": True,
                "reason": "agent_unavailable",
            }

            exec_state["answer_search"] = payload
            state["answer_search"] = payload
            _merge_structured_outputs(state, {"answer_search": payload})

            _set_agent_output(state, "answer_search", payload)
            _ensure_agent_outputs_nonempty(state, "answer_search", payload["answer_text"])

            emit_agent_execution_completed(
                event_category=EventCategory.EXECUTION,
                workflow_id=execution_id,
                agent_name="answer_search",
                success=True,
                output_context={"fallback": True, "thread_id": thread_id, "execution_id": execution_id},
                correlation_id=correlation_id,
                metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
            )

            return {
                "execution_state": exec_state,
                "answer_search": payload,
                "successful_agents": ["answer_search"],
                "structured_outputs": state.get("structured_outputs", {}) or {},
            }

        context = await convert_state_to_context(state)
        result_context = await agent.run_with_retry(context)

        raw = result_context.agent_outputs.get("answer_search", "") or ""
        payload = result_context.execution_state.get("answer_search_payload")
        if not isinstance(payload, dict):
            payload = {
                "ok": True,
                "type": "answer_search",
                "answer_text": raw or "(no answer produced)",
                "sources": result_context.execution_state.get("sources", []) or [],
                "timestamp": _now_iso(),
            }

        exec_state["answer_search"] = payload
        state["answer_search"] = payload
        _merge_structured_outputs(state, {"answer_search": payload})

        _set_agent_output(state, "answer_search", payload)
        _ensure_agent_outputs_nonempty(
            state, "answer_search", str(payload.get("answer_text") or raw or "ok")
        )

        emit_agent_execution_completed(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name="answer_search",
            success=True,
            output_context={"thread_id": thread_id, "execution_id": execution_id},
            correlation_id=correlation_id,
            metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
        )

        return {
            "execution_state": exec_state,
            "answer_search": payload,
            "successful_agents": ["answer_search"],
            "structured_outputs": state.get("structured_outputs", {}) or {},
        }

    except Exception as e:
        emit_agent_execution_completed(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name="answer_search",
            success=False,
            output_context={"error": str(e), "thread_id": thread_id, "execution_id": execution_id},
            error_message=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
            metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
        )
        record_agent_error(state, "answer_search", e)
        raise NodeExecutionError(f"answer_search execution failed: {e}") from e


@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def format_response_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    """
    Formats the allowed response for your API/UI.
    Terminates the workflow (GraphFactory edges go to END).

    ✅ Updated:
    - Prefer data_views output (if present)
    - Else fall back to answer_search (existing behavior)
    """
    exec_state = _ensure_exec_state_dict(state)

    # Prefer data_views output if available
    dv_payload = state.get("data_views") or exec_state.get("data_views")
    if isinstance(dv_payload, dict) and dv_payload:
        ui: Dict[str, Any] = {
            "status": "ok",
            "message": dv_payload.get("payload") or dv_payload.get("raw") or "",
            "sources": [],
            "timestamp": _now_iso(),
            "mode": "data_views",
        }
    else:
        answer_payload = state.get("answer_search") or exec_state.get("answer_search") or {}
        answer_text = ""
        sources: List[Any] = []
        if isinstance(answer_payload, dict):
            answer_text = str(answer_payload.get("answer_text") or "")
            sources = answer_payload.get("sources") or []

        ui = {
            "status": "ok",
            "message": answer_text,
            "sources": sources if isinstance(sources, list) else [],
            "timestamp": _now_iso(),
            "mode": "answer_search",
        }

    exec_state["format_response"] = {"ui": ui}
    exec_state["final_response"] = ui

    state["final_response"] = ui
    state["ui_response"] = ui  # optional legacy convenience
    _merge_structured_outputs(state, {"final_response": ui})

    _set_agent_output(state, "format_response", ui)
    _ensure_agent_outputs_nonempty(state, "format_response", str(ui.get("message") or "ok"))

    return {
        "execution_state": exec_state,
        "final_response": ui,
        "successful_agents": ["format_response"],
        "structured_outputs": state.get("structured_outputs", {}) or {},
    }


@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def format_block_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    exec_state = _ensure_exec_state_dict(state)

    guard_payload = state.get("guard") or exec_state.get("guard") or {}
    msg = "Sorry, I can’t help with that request."
    if isinstance(guard_payload, dict):
        msg = str(
            guard_payload.get("safe_response")
            or guard_payload.get("message")
            or guard_payload.get("reason")
            or msg
        )

    ui: Dict[str, Any] = {
        "status": "blocked",
        "message": msg,
        "sources": [],
        "timestamp": _now_iso(),
    }

    exec_state["format_block"] = {"ui": ui}
    exec_state["final_response"] = ui

    state["final_response"] = ui
    state["ui_response"] = ui
    _merge_structured_outputs(state, {"final_response": ui})

    _set_agent_output(state, "format_block", ui)
    _ensure_agent_outputs_nonempty(state, "format_block", msg)

    return {
        "execution_state": exec_state,
        "final_response": ui,
        "successful_agents": ["format_block"],
        "structured_outputs": state.get("structured_outputs", {}) or {},
    }


@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def format_requires_confirmation_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    exec_state = _ensure_exec_state_dict(state)

    guard_payload = state.get("guard") or exec_state.get("guard") or {}
    msg = "This request requires confirmation to proceed."
    if isinstance(guard_payload, dict):
        msg = str(guard_payload.get("reason") or guard_payload.get("message") or msg)

    ui: Dict[str, Any] = {
        "status": "requires_confirmation",
        "message": msg,
        "sources": [],
        "timestamp": _now_iso(),
    }

    exec_state["format_requires_confirmation"] = {"ui": ui}
    exec_state["final_response"] = ui

    state["final_response"] = ui
    state["ui_response"] = ui
    _merge_structured_outputs(state, {"final_response": ui})

    _set_agent_output(state, "format_requires_confirmation", ui)
    _ensure_agent_outputs_nonempty(state, "format_requires_confirmation", msg)

    return {
        "execution_state": exec_state,
        "final_response": ui,
        "successful_agents": ["format_requires_confirmation"],
        "structured_outputs": state.get("structured_outputs", {}) or {},
    }


# ---------------------------------------------------------------------
# Existing nodes (updated): data_view_node
# ---------------------------------------------------------------------

@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def data_view_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    """
    LangGraph node wrapper for DataViewAgent.

    ✅ Updated behavior (Option B):
    - Does NOT require synthesis output.
    - Prefers synthesis output if present.
    - Else falls back to answer_search output if present.
    - Else falls back to raw query + query_profile / routing_decision if present.

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
        emit_agent_execution_started(
            event_category=EventCategory.EXECUTION,
            workflow_id=workflow_id,
            agent_name="data_views",
            input_context={
                "query": original_query or state.get("query", ""),
                "node_type": "data_views",
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
            agent = await create_agent_with_llm("data_views")
        except Exception as e:
            logger.warning(f"DataView agent not available; data_view_node is a no-op: {e}")
            exec_state = _ensure_exec_state_dict(state)

            data_view_state = {"status": "skipped", "reason": "agent_not_registered"}
            exec_state["data_views"] = data_view_state
            state["data_views"] = data_view_state
            _merge_structured_outputs(state, {"data_views": data_view_state})

            return {
                "execution_state": exec_state,
                "data_views": data_view_state,
                "successful_agents": [],
                "structured_outputs": state.get("structured_outputs", {}) or {},
            }

        # Build AgentContext as usual...
        context = await convert_state_to_context(state)

        refined = ""
        try:
            if state.get("refiner"):
                refined = cast(RefinerState, state["refiner"]).get("refined_question", "")  # type: ignore[arg-type]
        except Exception:
            refined = ""

        effective_query = refined or (original_query or state.get("query", "") or context.query)
        _record_effective_query(state, "data_views", effective_query)

        # ---------------------------
        # ✅ Option B: flexible inputs
        # ---------------------------
        synthesis_state = _first_present(state, "synthesis")
        answer_state = _first_present(state, "answer_search")
        query_profile = _first_present(state, "query_profile") or {}
        routing_decision = _first_present(state, "routing_decision") or {}

        # Prefer synthesis.final_analysis if available
        dv_input: Dict[str, Any]
        if isinstance(synthesis_state, dict) and synthesis_state.get("final_analysis"):
            dv_input = {
                "source": "synthesis",
                "input": synthesis_state.get("final_analysis"),
                "query": effective_query,
                "query_profile": query_profile,
                "routing_decision": routing_decision,
            }
        # Else prefer answer_search.answer_text if available
        elif isinstance(answer_state, dict) and (
            answer_state.get("answer_text") or answer_state.get("sources") is not None
        ):
            dv_input = {
                "source": "answer_search",
                "input": answer_state.get("answer_text") or "",
                "sources": answer_state.get("sources") or [],
                "query": effective_query,
                "query_profile": query_profile,
                "routing_decision": routing_decision,
            }
        # Else raw fallback
        else:
            dv_input = {
                "source": "raw",
                "input": {"query": effective_query, "query_profile": query_profile, "routing_decision": routing_decision},
                "query": effective_query,
                "query_profile": query_profile,
                "routing_decision": routing_decision,
            }

        # Inject the payload so the agent can consume it without relying on strict upstream nodes.
        # This keeps backward compatibility with your agents by using execution_state as an input channel.
        context.execution_state["data_view_input"] = dv_input

        # Run DataViews agent
        result_context = await agent.run_with_retry(context)
        data_view_raw_output = result_context.agent_outputs.get("data_views", "")

        view_payload = result_context.execution_state.get("data_view_payload")
        if view_payload is None:
            # fallback: agent may store structured outputs generically
            view_payload = result_context.execution_state.get("structured_outputs")

        data_view_state: Dict[str, Any] = {
            "payload": view_payload,
            "raw": truncate_for_websocket_event(str(data_view_raw_output), "data_views"),
            "input_source": dv_input.get("source"),
            "timestamp": _now_iso(),
        }

        token_usage = result_context.get_agent_token_usage("data_views")

        emit_agent_execution_completed(
            event_category=EventCategory.EXECUTION,
            workflow_id=workflow_id,
            agent_name="data_views",
            success=True,
            output_context={
                "node_type": "data_views",
                "thread_id": thread_id,
                "execution_id": execution_id,
                "has_payload": bool(view_payload),
                "input_source": dv_input.get("source"),
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
        exec_state = _ensure_exec_state_dict(state)

        exec_state["data_views"] = data_view_state
        state["data_views"] = data_view_state
        _merge_structured_outputs(state, {"data_views": data_view_state})

        # Legacy agent output storage
        _set_agent_output(state, "data_views", data_view_state)
        _ensure_agent_outputs_nonempty(state, "data_views", str(data_view_state.get("raw") or "ok"))

        return {
            "execution_state": exec_state,
            "data_views": data_view_state,
            "successful_agents": ["data_views"],
            "structured_outputs": structured_outputs,
        }

    except Exception as e:
        logger.error(f"data_views node failed: {e}")
        emit_agent_execution_completed(
            event_category=EventCategory.EXECUTION,
            workflow_id=workflow_id,
            agent_name="data_views",
            success=False,
            output_context={
                "error": str(e),
                "node_type": "data_views",
                "thread_id": thread_id,
                "execution_id": execution_id,
            },
            error_message=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
            metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
        )
        record_agent_error(state, "data_views", e)
        raise NodeExecutionError(f"DataView execution failed: {e}") from e


async def handle_node_timeout(
    coro: Coroutine[Any, Any, Any], timeout_seconds: float = 30.0
) -> Any:
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise NodeExecutionError(f"Node execution timed out after {timeout_seconds}s")


def get_node_dependencies() -> Dict[str, List[str]]:
    # ✅ Updated to reflect Option B: data_views can run with just guard/answer_search/raw
    return {
        "guard": [],
        "answer_search": ["guard"],
        "format_response": ["answer_search"],  # data_views path still OK (format_response checks)
        "format_block": ["guard"],
        "format_requires_confirmation": ["guard"],

        "refiner": [],
        "critic": ["refiner"],
        "historian": ["refiner"],
        "synthesis": ["critic"],  # historian optional

        # IMPORTANT: use your canonical node key, which is "data_views" in build_graph.py
        "data_views": [],  # Option B: no hard deps
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
    "answer_search_node",
    "format_response_node",
    "format_block_node",
    "format_requires_confirmation_node",
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
