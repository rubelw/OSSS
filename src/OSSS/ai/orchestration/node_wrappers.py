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
import json
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
    DataQueryState,
    record_agent_error,
)
from OSSS.ai.observability import get_logger
from OSSS.ai.orchestration.canonicalization import (
    extract_refined_question,
    canonicalize_dcg,
)
from OSSS.ai.llm.factory import LLMFactory
from OSSS.ai.orchestration.routing import (
    should_run_historian,
    DBQueryRouter,
)

logger = get_logger(__name__)

# Global timing registry to store node execution times
_TIMING_REGISTRY: Dict[str, Dict[str, float]] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _canon_agent_key(name: str) -> str:
    return (name or "").strip().lower().replace("-", "_")


def _ensure_exec_state(state: Dict[str, Any]) -> Dict[str, Any]:
    exec_state = state.get("execution_state")
    if not isinstance(exec_state, dict):
        exec_state = {}
        state["execution_state"] = exec_state
    return exec_state


def _get_execution_config(state: Dict[str, Any], runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    """
    Best-effort extraction of execution config for nodes.
    Priority:
      1) runtime.context.execution_config (if you add it later)
      2) state["execution_state"]["execution_config"]
      3) state["execution_metadata"]["execution_config"]
    """
    ctx_cfg = getattr(runtime.context, "execution_config", None)
    if isinstance(ctx_cfg, dict):
        return ctx_cfg

    exec_state = state.get("execution_state")
    if isinstance(exec_state, dict):
        ec = exec_state.get("execution_config")
        if isinstance(ec, dict):
            return ec

    meta = state.get("execution_metadata")
    if isinstance(meta, dict):
        ec = meta.get("execution_config")
        if isinstance(ec, dict):
            return ec

    return {}


def _record_effective_query(state: dict, agent_name: str, effective_query: str) -> None:
    exec_state = _ensure_exec_state(state)
    eq = exec_state.setdefault("effective_queries", {})
    if isinstance(eq, dict):
        eq[_canon_agent_key(agent_name)] = effective_query


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, default=str)
    return str(value)


def _pick_latest_data_query_node_id(state: OSSSState) -> Optional[str]:
    """
    Option A: return the most recently completed data_query:* node id if present,
    else fall back to last planned, else None.
    """
    completed = state.get("completed_data_query_nodes")
    if isinstance(completed, list) and completed:
        last = completed[-1]
        if isinstance(last, str) and last:
            return last

    planned = state.get("planned_data_query_nodes")
    if isinstance(planned, list) and planned:
        last = planned[-1]
        if isinstance(last, str) and last:
            return last

    return None


def _pick_latest_data_query_payload(state: OSSSState) -> Any:
    """
    Option A: get payload from data_query_results for the latest node id.
    Falls back to legacy state['data_query'].result.
    """
    node_id = _pick_latest_data_query_node_id(state)

    dqr = state.get("data_query_results")
    if node_id and isinstance(dqr, dict) and node_id in dqr:
        return dqr.get(node_id)

    dq_state = state.get("data_query")
    if isinstance(dq_state, dict):
        return dq_state.get("result")

    return None


def get_timing_registry() -> Dict[str, Dict[str, float]]:
    return _TIMING_REGISTRY.copy()


def clear_timing_registry() -> None:
    _TIMING_REGISTRY.clear()


def register_node_timing(execution_id: str, node_name: str, execution_time_seconds: float) -> None:
    if execution_id not in _TIMING_REGISTRY:
        _TIMING_REGISTRY[execution_id] = {}
    _TIMING_REGISTRY[execution_id][node_name] = execution_time_seconds


class NodeExecutionError(Exception):
    """Raised when a node execution fails."""
    pass


F = TypeVar("F", bound=Callable[..., Coroutine[Any, Any, Any]])


class CircuitBreakerFunction(Protocol):
    _failure_count: int
    _circuit_open: bool
    _last_failure_time: Optional[float]

    def __call__(self, *args: Any, **kwargs: Any) -> Coroutine[Any, Any, Any]: ...


def circuit_breaker(max_failures: int = 3, reset_timeout: float = 300.0) -> Callable[[F], F]:
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
                circuit_state["last_failure_time"] = getattr(wrapper, "_last_failure_time")
            if hasattr(wrapper, "_circuit_open"):
                circuit_state["circuit_open"] = getattr(wrapper, "_circuit_open")

            if circuit_state["circuit_open"]:
                if circuit_state["last_failure_time"]:
                    time_since_failure = time.time() - cast(float, circuit_state["last_failure_time"])
                    if time_since_failure < reset_timeout:
                        raise NodeExecutionError(
                            f"Circuit breaker open for {func.__name__}. "
                            f"Retry in {reset_timeout - time_since_failure:.1f}s"
                        )
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
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        node_name = func.__name__.replace("_node", "")

        try:
            logger.info(f"Starting execution of {node_name} node")
            result = await func(*args, **kwargs)

            execution_time_ms = (time.time() - start_time) * 1000
            execution_time_seconds = execution_time_ms / 1000
            logger.info(f"Completed {node_name} node execution in {execution_time_ms:.2f}ms")

            execution_id = None
            if args and isinstance(args[0], dict):
                state = args[0]
                if isinstance(state.get("execution_metadata"), dict):
                    execution_id = state["execution_metadata"].get("execution_id")
                if not execution_id and isinstance(state.get("execution_state"), dict):
                    execution_id = state["execution_state"].get("execution_id")

            if execution_id:
                register_node_timing(str(execution_id), node_name, execution_time_seconds)

            if isinstance(result, dict):
                result.setdefault("_node_execution_times", {})
                result["_node_execution_times"][node_name] = {
                    "execution_time_seconds": execution_time_seconds,
                    "execution_time_ms": execution_time_ms,
                    "completed": True,
                }

            return result
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Failed {node_name} node execution after {execution_time_ms:.2f}ms: {e}")
            raise

    return cast(F, wrapper)


# ---------------------------------------------------------------------------
# Agent creation + State <-> Context conversion
# ---------------------------------------------------------------------------

async def create_agent_with_llm(
    agent_name: str,
    *,
    state: Optional[Dict[str, Any]] = None,
    runtime: Optional[Runtime[OSSSContext]] = None,
) -> BaseAgent:
    registry = get_agent_registry()
    agent_name_lower = _canon_agent_key(agent_name)

    exec_cfg: Dict[str, Any] = {}
    if state is not None and runtime is not None:
        exec_cfg = _get_execution_config(state, runtime)

    if agent_name_lower == "classifier":
        classifier_cfg = exec_cfg.get("classifier", {}) if isinstance(exec_cfg, dict) else {}
        if not isinstance(classifier_cfg, dict):
            classifier_cfg = {}

        model_path = classifier_cfg.get("model_path", "models/intent_classifier.joblib")
        model_version = classifier_cfg.get("model_version", "v1")

        logger.info(
            "Creating classifier agent",
            extra={"agent_name": "classifier", "model_path": str(model_path), "model_version": model_version},
        )
        return registry.create_agent(agent_name_lower, model_path=model_path, model_version=model_version)

    if agent_name_lower == "data_query":
        return registry.create_agent(agent_name_lower)

    llm = LLMFactory.create(agent_name=agent_name_lower, execution_config=exec_cfg)

    agent_config_kwargs: Dict[str, Any] = {}
    from OSSS.ai.config.agent_configs import HistorianConfig, RefinerConfig, CriticConfig, SynthesisConfig

    if agent_name_lower == "historian":
        agent_config_kwargs["config"] = HistorianConfig()
    elif agent_name_lower == "refiner":
        agent_config_kwargs["config"] = RefinerConfig()
    elif agent_name_lower == "critic":
        agent_config_kwargs["config"] = CriticConfig()
    elif agent_name_lower == "synthesis":
        agent_config_kwargs["config"] = SynthesisConfig()

    agent = registry.create_agent(agent_name_lower, llm=llm, **agent_config_kwargs)

    if agent_name_lower == "historian":
        agent.timeout_seconds = HistorianConfig().execution_config.timeout_seconds
    elif agent_name_lower == "refiner":
        agent.timeout_seconds = RefinerConfig().execution_config.timeout_seconds
    elif agent_name_lower == "critic":
        agent.timeout_seconds = CriticConfig().execution_config.timeout_seconds
    elif agent_name_lower == "synthesis":
        agent.timeout_seconds = SynthesisConfig().execution_config.timeout_seconds

    return agent


async def convert_state_to_context(state: OSSSState) -> AgentContext:
    """
    Convert LangGraph state to AgentContext for agent execution.

    Cleanups applied:
      - Do NOT add duplicate outputs (no "Refiner"/"DataQuery" alias keys)
      - Do NOT re-add outputs that BaseAgent already writes during this run
      - Only hydrate context from prior state to support downstream nodes

    Option A:
      - Prefer data_query_results/latest completed node over legacy state["data_query"]
    """
    _ = AgentContextStateBridge()  # retained for future compatibility

    if "query" not in state:
        raise ValueError("State must contain a query field")

    query = state.get("query", "") or ""
    context = AgentContext(query=query)

    # Carry forward execution_state bits
    state_exec = state.get("execution_state", {})
    if isinstance(state_exec, dict):
        for k in (
            "agent_output_meta",
            "effective_queries",
            "rag_context",
            "rag_hits",
            "rag_meta",
            "rag_enabled",
            "route_key",
            "route",
            "route_reason",
            "route_locked",
        ):
            v = state_exec.get(k)
            if v is not None:
                context.execution_state[k] = v

    so = state.get("structured_outputs")
    if isinstance(so, dict):
        context.execution_state["structured_outputs"] = so

    # Hydrate prior outputs for downstream nodes.
    # IMPORTANT: use canonical lowercase keys only.
    if state.get("refiner"):
        refiner_state: Optional[RefinerState] = state["refiner"]
        if refiner_state is not None:
            refined_question = refiner_state.get("refined_question", "")
            if refined_question:
                context.add_agent_output("refiner", refined_question)
                context.execution_state["refiner_topics"] = refiner_state.get("topics", [])
                context.execution_state["refiner_confidence"] = refiner_state.get("confidence", 0.8)

    # ✅ Option A: hydrate data_query from data_query_results (latest completed)
    latest_payload = _pick_latest_data_query_payload(state)
    if latest_payload is not None:
        context.add_agent_output("data_query", _to_text(latest_payload))
        context.execution_state["data_query_result"] = latest_payload
        latest_node_id = _pick_latest_data_query_node_id(state)
        if latest_node_id:
            context.execution_state["data_query_node_id"] = latest_node_id
    else:
        # Legacy fallback
        if state.get("data_query"):
            dq_state: Optional[DataQueryState] = state["data_query"]  # type: ignore[assignment]
            if dq_state is not None:
                result = dq_state.get("result", "")
                context.add_agent_output("data_query", _to_text(result))
                context.execution_state["data_query_result"] = dq_state.get("result")

    if state.get("critic"):
        critic_state: Optional[CriticState] = state["critic"]
        if critic_state is not None:
            critique = critic_state.get("critique", "")
            if critique:
                context.add_agent_output("critic", critique)
                context.execution_state["critic_suggestions"] = critic_state.get("suggestions", [])
                context.execution_state["critic_severity"] = critic_state.get("severity", "medium")

    if state.get("historian"):
        historian_state: Optional[HistorianState] = state["historian"]
        if historian_state is not None:
            historical_summary = historian_state.get("historical_summary", "")
            if historical_summary:
                context.add_agent_output("historian", historical_summary)
                context.execution_state["historian_retrieved_notes"] = historian_state.get("retrieved_notes", [])
                context.execution_state["historian_search_strategy"] = historian_state.get("search_strategy", "hybrid")
                context.execution_state["historian_topics_found"] = historian_state.get("topics_found", [])
                context.execution_state["historian_confidence"] = historian_state.get("confidence", 0.8)

    # Add execution metadata (best-effort)
    execution_metadata = state.get("execution_metadata", {})
    if isinstance(execution_metadata, dict) and execution_metadata:
        context.execution_state.update(
            {
                "execution_id": execution_metadata.get("execution_id", ""),
                "orchestrator_type": "langgraph-real",
                "successful_agents": state.get("successful_agents", []).copy() if isinstance(state.get("successful_agents"), list) else [],
                "failed_agents": state.get("failed_agents", []).copy() if isinstance(state.get("failed_agents"), list) else [],
            }
        )

    return context


# ---------------------------------------------------------------------------
# Routing node
# ---------------------------------------------------------------------------

@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def route_gate_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    thread_id = runtime.context.thread_id
    execution_id = runtime.context.execution_id
    original_query = runtime.context.query
    correlation_id = runtime.context.correlation_id
    checkpoint_enabled = runtime.context.enable_checkpoints

    logger.info(
        f"Executing route_gate node in thread {thread_id}",
        extra={
            "thread_id": thread_id,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
            "query_length": len(original_query or ""),
            "checkpoint_enabled": checkpoint_enabled,
        },
    )

    context = await convert_state_to_context(state)

    router = DBQueryRouter(data_query_target="data_query", default_target="refiner")
    chosen_target = router(context)
    route_key = "action" if chosen_target == "data_query" else "informational"

    exec_state = _ensure_exec_state(state)
    exec_state["route_key"] = route_key
    exec_state["route"] = chosen_target

    for k in ("route_reason", "route_locked"):
        v = context.execution_state.get(k)
        if v is not None:
            exec_state[k] = v

    try:
        context.log_trace(
            agent_name="route_gate",
            input={"query": original_query or state.get("query", "")},
            output={
                "route_key": route_key,
                "chosen_target": chosen_target,
                "route_reason": exec_state.get("route_reason"),
                "route_locked": exec_state.get("route_locked"),
            },
        )
    except Exception:
        pass

    logger.info(
        "Route chosen",
        extra={
            "thread_id": thread_id,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
            "route_key": route_key,
            "chosen_target": chosen_target,
            "route_reason": exec_state.get("route_reason"),
        },
    )

    return {"execution_state": exec_state, "route_key": route_key, "route": chosen_target}


# ---------------------------------------------------------------------------
# Node wrappers
# ---------------------------------------------------------------------------

@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def refiner_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
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

    try:
        agent = await create_agent_with_llm("refiner", state=state, runtime=runtime)
        context = await convert_state_to_context(state)

        effective_query = original_query or state.get("query", "") or context.query
        _record_effective_query(state, "refiner", effective_query)

        # ✅ Critical: pass the *instance* context (never AgentContext type)
        result_context = await agent.run_with_retry(context)

        # Extract refiner output (canonical key only)
        refiner_raw_output = (result_context.agent_outputs.get("refiner") or "").strip()

        # Hard-guard to a single refined question + canonicalize DCG
        refined_question = canonicalize_dcg(extract_refined_question(refiner_raw_output))

        refiner_state = RefinerState(
            refined_question=refined_question,
            topics=result_context.execution_state.get("topics", []),
            confidence=result_context.execution_state.get("confidence", 0.8),
            processing_notes=result_context.execution_state.get("processing_notes"),
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_output_meta=result_context.execution_state.get("agent_output_meta", {}),
        )

        structured_outputs = result_context.execution_state.get("structured_outputs", {})

        exec_state = _ensure_exec_state(state)
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
        record_agent_error(state, "refiner", e)
        raise NodeExecutionError(f"Refiner execution failed: {e}") from e


@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def data_query_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    """
    Option A compliance:
      - MUST append node id into completed_data_query_nodes
      - MUST merge payload into data_query_results under that node id
    """
    thread_id = runtime.context.thread_id
    execution_id = runtime.context.execution_id
    original_query = runtime.context.query
    correlation_id = runtime.context.correlation_id
    checkpoint_enabled = runtime.context.enable_checkpoints

    logger.info(
        f"Executing data_query node in thread {thread_id}",
        extra={
            "thread_id": thread_id,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
            "query_length": len(original_query or ""),
            "checkpoint_enabled": checkpoint_enabled,
        },
    )

    try:
        agent = await create_agent_with_llm("data_query", state=state, runtime=runtime)
        context = await convert_state_to_context(state)

        refined = ""
        try:
            if state.get("refiner"):
                refined = cast(RefinerState, state["refiner"]).get("refined_question", "")  # type: ignore[arg-type]
        except Exception:
            refined = ""

        effective_query = refined or (original_query or state.get("query", "") or context.query)
        _record_effective_query(state, "data_query", effective_query)

        result_context = await agent.run_with_retry(context)

        # Find dynamic key like data_query:<view> (preferred node id)
        agent_outputs = getattr(result_context, "agent_outputs", {}) or {}
        dq_value: Any = None
        dq_node_id: str = "data_query"  # fallback

        if isinstance(agent_outputs, dict):
            for k, v in agent_outputs.items():
                if isinstance(k, str) and k.startswith("data_query:"):
                    dq_node_id = k
                    dq_value = v
                    break

        if dq_value is None and isinstance(agent_outputs, dict):
            dq_value = agent_outputs.get("data_query")

        # Prefer structured payload if present
        payload: Any = None
        if isinstance(getattr(result_context, "execution_state", None), dict):
            payload = result_context.execution_state.get("data_query_result")
            if payload is None:
                # fall back to whatever the agent emitted
                payload = dq_value

            # Keep a "data_view" convenience if useful downstream
            if "data_view" not in result_context.execution_state and payload is not None:
                result_context.execution_state["data_view"] = payload
        else:
            payload = dq_value

        canonical_value = payload if payload is not None else ""

        # Ensure meta has canonical entry (UI often keys off this)
        if isinstance(getattr(result_context, "execution_state", None), dict):
            aom = result_context.execution_state.setdefault("agent_output_meta", {})
            if isinstance(aom, dict):
                aom.setdefault("data_query", {"agent": "data_query", "action": "read"})
                if dq_node_id != "data_query":
                    aom.setdefault(dq_node_id, {"agent": dq_node_id, "action": "read", "alias": "data_query"})

        data_query_state = DataQueryState(
            query=effective_query,
            result=canonical_value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_output_meta=result_context.execution_state.get("agent_output_meta", {})
            if isinstance(getattr(result_context, "execution_state", None), dict)
            else {},
        )

        structured_outputs = (
            result_context.execution_state.get("structured_outputs", {})
            if isinstance(getattr(result_context, "execution_state", None), dict)
            else {}
        )

        exec_state = _ensure_exec_state(state)

        successful = ["data_query"]
        if dq_node_id != "data_query":
            successful.append(dq_node_id)

        # ------------------------------------------------------------------
        # ✅ Option A state updates (CRITICAL):
        # reducers apply because we return these keys
        # ------------------------------------------------------------------
        option_a_updates: Dict[str, Any] = {
            "completed_data_query_nodes": [dq_node_id],
            "data_query_results": {dq_node_id: canonical_value},
        }

        # Keep planned list best-effort if router didn't fill it (no reducer here, so only set when empty)
        planned = state.get("planned_data_query_nodes")
        if (not isinstance(planned, list)) or (len(planned) == 0):
            option_a_updates["planned_data_query_nodes"] = [dq_node_id]

        return {
            "execution_state": exec_state,
            "data_query": data_query_state,  # legacy compatibility
            "successful_agents": successful,
            "structured_outputs": structured_outputs,
            **option_a_updates,
        }

    except Exception as e:
        logger.error(
            f"data_query node failed: {e}",
            extra={
                "thread_id": thread_id,
                "execution_id": execution_id,
                "correlation_id": correlation_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        record_agent_error(state, "data_query", e)
        raise NodeExecutionError(f"data_query execution failed: {e}") from e


@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def critic_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
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

        agent = await create_agent_with_llm("critic", state=state, runtime=runtime)
        context = await convert_state_to_context(state)

        refined = ""
        try:
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
            agent_output_meta=result_context.execution_state.get("agent_output_meta", {}),
        )

        structured_outputs = result_context.execution_state.get("structured_outputs", {})

        exec_state = _ensure_exec_state(state)
        return {
            "execution_state": exec_state,
            "critic": critic_state,
            "successful_agents": ["critic"],
            "structured_outputs": structured_outputs,
        }

    except Exception as e:
        logger.error(f"Critic node failed: {e}")
        record_agent_error(state, "critic", e)
        raise NodeExecutionError(f"Critic execution failed: {e}") from e


@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def historian_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
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

    # Optional skip
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

        exec_state = _ensure_exec_state(state)
        return {
            "execution_state": exec_state,
            "historian": None,
            "successful_agents": [],
            "structured_outputs": state.get("structured_outputs", {}) or {},
        }

    try:
        if not state.get("refiner"):
            raise NodeExecutionError("Historian node requires refiner output")

        agent = await create_agent_with_llm("historian", state=state, runtime=runtime)
        context = await convert_state_to_context(state)

        refined = ""
        try:
            refined = cast(RefinerState, state["refiner"]).get("refined_question", "")  # type: ignore[arg-type]
        except Exception:
            refined = ""

        effective_query = refined or (original_query or state.get("query", "") or context.query)
        _record_effective_query(state, "historian", effective_query)

        result_context = await agent.run_with_retry(context)

        historian_raw_output = result_context.agent_outputs.get("historian", "")
        retrieved_notes = getattr(result_context, "retrieved_notes", [])
        topics_found = result_context.execution_state.get("topics_found", []) if isinstance(result_context.execution_state, dict) else []

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
            agent_output_meta=result_context.execution_state.get("agent_output_meta", {}),
        )

        structured_outputs = result_context.execution_state.get("structured_outputs", {})

        exec_state = _ensure_exec_state(state)
        return {
            "execution_state": exec_state,
            "historian": historian_state,
            "successful_agents": ["historian"],
            "structured_outputs": structured_outputs,
        }

    except Exception as e:
        logger.error(f"Historian node failed: {e}")
        record_agent_error(state, "historian", e)
        raise NodeExecutionError(f"Historian execution failed: {e}") from e


@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def synthesis_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    """
    Synthesis is now safe in "action mode":
      - if data_query exists, return it as final analysis WITHOUT calling LLM
      - otherwise run synthesis LLM using whatever signals exist

    Option A:
      - Prefer state['data_query_results'] (latest completed) over context.agent_outputs['data_query']
    """
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

        context = await convert_state_to_context(state)

        critic_text = (context.agent_outputs.get("critic") or "").strip()
        historian_text = (context.agent_outputs.get("historian") or "").strip()

        # ✅ Option A: pull latest data_query payload from state
        dq_payload = _pick_latest_data_query_payload(state)
        data_query_text = _to_text(dq_payload) if dq_payload is not None else ""

        if data_query_text:
            mode = "action"
        elif critic_text or historian_text:
            mode = "reflection"
        else:
            mode = "fallback"

        # Only enforce historian when your heuristic says it is required AND it was explicitly skipped (None)
        if mode in {"reflection", "fallback"} and not historian_text:
            if should_run_historian(original_query or "") and state.get("historian") is None:
                raise NodeExecutionError("Synthesis node requires historian output for this query")
            logger.info("Proceeding without historian output (skipped by routing)")

        if not critic_text:
            logger.info("Proceeding without critic output (skipped by routing)")

        refined = ""
        try:
            refined = cast(RefinerState, state["refiner"]).get("refined_question", "")  # type: ignore[arg-type]
        except Exception:
            refined = ""

        effective_query = refined or (original_query or state.get("query", "") or context.query)
        _record_effective_query(state, "synthesis", effective_query)

        synthesis_raw_output = ""

        if mode == "action":
            synthesis_raw_output = data_query_text

            # Ensure synthesis channel exists for UI/API
            context.add_agent_output("synthesis", synthesis_raw_output)

            if isinstance(context.execution_state, dict):
                aom = context.execution_state.get("agent_output_meta")
                if not isinstance(aom, dict):
                    aom = {}
                    context.execution_state["agent_output_meta"] = aom

                latest_node_id = _pick_latest_data_query_node_id(state)
                aom["synthesis"] = {
                    "agent": "synthesis",
                    "mode": "action",
                    "source": "data_query_results",
                    "data_query_node_id": latest_node_id,
                    "action": "read",
                    "llm_used": False,
                }

        else:
            agent = await create_agent_with_llm("synthesis", state=state, runtime=runtime)

            # ✅ Critical: pass the *instance* context (never AgentContext type)
            result_context = await agent.run_with_retry(context)

            context = result_context
            synthesis_raw_output = (context.agent_outputs.get("synthesis") or "").strip()

            if isinstance(context.execution_state, dict):
                context.execution_state.setdefault("synthesis_metadata", {})
                context.execution_state["synthesis_metadata"].update({"mode": mode, "llm_used": True})

        sources_used: List[str] = []
        if state.get("refiner"):
            sources_used.append("refiner")
        if data_query_text:
            sources_used.append("data_query")
        if critic_text:
            sources_used.append("critic")
        if historian_text:
            sources_used.append("historian")

        synthesis_state = SynthesisState(
            final_analysis=synthesis_raw_output,
            key_insights=context.execution_state.get("key_insights", []) if isinstance(context.execution_state, dict) else [],
            sources_used=sources_used,
            themes_identified=context.execution_state.get("themes", []) if isinstance(context.execution_state, dict) else [],
            conflicts_resolved=context.execution_state.get("conflicts_resolved", 0) if isinstance(context.execution_state, dict) else 0,
            confidence=context.execution_state.get("confidence", 0.8) if isinstance(context.execution_state, dict) else 0.8,
            metadata=context.execution_state.get("synthesis_metadata", {"mode": mode}) if isinstance(context.execution_state, dict) else {"mode": mode},
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_output_meta=context.execution_state.get("agent_output_meta", {}) if isinstance(context.execution_state, dict) else {},
        )

        structured_outputs = context.execution_state.get("structured_outputs", {}) if isinstance(context.execution_state, dict) else {}

        exec_state = _ensure_exec_state(state)

        agent_outputs = getattr(context, "agent_outputs", {}) or {}
        agent_output_meta = {}
        if isinstance(context.execution_state, dict):
            aom = context.execution_state.get("agent_output_meta")
            if isinstance(aom, dict):
                agent_output_meta = aom

        return {
            "execution_state": exec_state,
            "synthesis": synthesis_state,
            "successful_agents": ["synthesis"],
            "structured_outputs": structured_outputs,
            # Optional convenience for API/UI immediate rendering
            "agent_outputs": agent_outputs,
            "agent_output_meta": agent_output_meta,
        }

    except Exception as e:
        logger.error(f"Synthesis node failed: {e}")
        record_agent_error(state, "synthesis", e)
        raise NodeExecutionError(f"Synthesis execution failed: {e}") from e


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

async def handle_node_timeout(coro: Coroutine[Any, Any, Any], timeout_seconds: float = 30.0) -> Any:
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise NodeExecutionError(f"Node execution timed out after {timeout_seconds}s")


def get_node_dependencies() -> Dict[str, List[str]]:
    return {
        "refiner": [],
        "data_query": [],
        "critic": ["refiner"],
        "historian": ["refiner"],
        "synthesis": ["refiner"],
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
    "route_gate_node",
    "refiner_node",
    "data_query_node",
    "critic_node",
    "historian_node",
    "synthesis_node",
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
