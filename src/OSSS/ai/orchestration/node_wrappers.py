"""
LangGraph node wrappers for OSSS agents.

Refactor goals (scalable + maintainable):
- Remove copy/paste across nodes via a generic node runner
- Centralize: event emission gating, effective query calculation, state merges, and error handling
- Keep backward compatibility: same node function names + __all__ exports
- Allow easy addition of new nodes by defining a NodeSpec

Notes:
- This file assumes OSSSState is a dict-like TypedDict and supports .get/.setdefault.
- Uses runtime.context.emit_events if present (defaults False) to reduce noisy event spam.
"""

import asyncio
import time
import inspect
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Protocol,
    TypeVar,
    Union,
    cast,
)

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
from OSSS.ai.events import emit_agent_execution_started, emit_agent_execution_completed
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
    exec_state = state.setdefault("execution_state", {})
    if not isinstance(exec_state, dict):
        exec_state = {}
        state["execution_state"] = exec_state
    return exec_state


def _ensure_list(state: OSSSState, key: str) -> List[Any]:
    v = state.get(key)
    if isinstance(v, list):
        return v
    state[key] = []
    return cast(List[Any], state[key])


def _merge_structured_outputs(state: OSSSState, patch: Dict[str, Any]) -> None:
    so = state.get("structured_outputs")
    if not isinstance(so, dict):
        state["structured_outputs"] = {}
        so = state["structured_outputs"]
    so.update(patch)


def _ensure_agent_outputs_nonempty(state: dict, agent_name: str, message: str) -> None:
    exec_state = state.setdefault("execution_state", {})
    if not isinstance(exec_state, dict):
        return
    aom = exec_state.setdefault("agent_outputs", {})
    if isinstance(aom, dict) and not aom:
        aom[agent_name] = message


def _set_agent_output(state: dict, agent_name: str, output: Any) -> None:
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


def _set_guard_decision(state: dict, decision: str) -> None:
    d = (decision or "").strip().lower()
    if d not in {"allow", "requires_confirmation", "block"}:
        d = "block"
    state["guard_decision"] = d


def _get_agent_output_meta(state: OSSSState) -> Dict[str, Any]:
    exec_state = _ensure_exec_state_dict(state)
    meta = exec_state.setdefault("agent_output_meta", {})
    if not isinstance(meta, dict):
        exec_state["agent_output_meta"] = {}
        meta = exec_state["agent_output_meta"]
    return meta


def _get_query_profile(state: OSSSState) -> Dict[str, Any]:
    meta = _get_agent_output_meta(state)
    qp = meta.get("_query_profile")
    return qp if isinstance(qp, dict) else {}


def _get_routing_meta(state: OSSSState) -> Dict[str, Any]:
    meta = _get_agent_output_meta(state)
    r = meta.get("_routing")
    return r if isinstance(r, dict) else {}


def _first_present(state: OSSSState, *keys: str) -> Optional[Any]:
    for k in keys:
        v = state.get(k)
        if v is not None:
            return v
    return None


async def _coerce_base_agent(agent: Any, agent_name: str) -> BaseAgent:
    if inspect.iscoroutine(agent):
        agent = await agent
    if not isinstance(agent, BaseAgent):
        raise TypeError(
            f"Agent '{agent_name}' constructor returned {type(agent)!r}, expected BaseAgent"
        )
    return agent


# ---------------------------------------------------------------------
# Timing registry helpers
# ---------------------------------------------------------------------
def get_timing_registry() -> Dict[str, Dict[str, float]]:
    return _TIMING_REGISTRY.copy()


def clear_timing_registry() -> None:
    global _TIMING_REGISTRY
    _TIMING_REGISTRY.clear()


def register_node_timing(execution_id: str, node_name: str, execution_time_seconds: float) -> None:
    global _TIMING_REGISTRY
    if execution_id not in _TIMING_REGISTRY:
        _TIMING_REGISTRY[execution_id] = {}
    _TIMING_REGISTRY[execution_id][node_name] = execution_time_seconds


class NodeExecutionError(Exception):
    """Raised when a node execution fails."""


# ---------------------------------------------------------------------
# Decorators: circuit breaker + metrics
# ---------------------------------------------------------------------
F = TypeVar("F", bound=Callable[..., Coroutine[Any, Any, Any]])


class CircuitBreakerFunction(Protocol):
    _failure_count: int
    _circuit_open: bool
    _last_failure_time: Optional[float]

    def __call__(self, *args: Any, **kwargs: Any) -> Coroutine[Any, Any, Any]:
        ...


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
                last = circuit_state.get("last_failure_time")
                if last:
                    dt = time.time() - cast(float, last)
                    if dt < reset_timeout:
                        raise NodeExecutionError(
                            f"Circuit breaker open for {func.__name__}. Retry in {reset_timeout - dt:.1f}s"
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
                circuit_state["failure_count"] = cast(int, circuit_state["failure_count"]) + 1
                circuit_state["last_failure_time"] = time.time()
                if cast(int, circuit_state["failure_count"]) >= max_failures:
                    circuit_state["circuit_open"] = True
                    logger.error(
                        f"Circuit breaker opened for {func.__name__} after {circuit_state['failure_count']} failures"
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
        start = time.time()
        node_name = func.__name__.replace("_node", "")
        try:
            logger.info(f"Starting execution of {node_name} node")
            result = await func(*args, **kwargs)

            ms = (time.time() - start) * 1000
            sec = ms / 1000.0
            logger.info(f"Completed {node_name} node execution in {ms:.2f}ms")

            # Store in result
            if isinstance(result, dict):
                times = result.setdefault("_node_execution_times", {})
                if isinstance(times, dict):
                    times[node_name] = {"execution_time_seconds": sec, "execution_time_ms": ms, "completed": True}

            # Optional global registry
            execution_id = None
            if args and isinstance(args[0], dict):
                st = args[0]
                meta = st.get("execution_metadata")
                if isinstance(meta, dict):
                    execution_id = meta.get("execution_id")
            if execution_id:
                register_node_timing(str(execution_id), node_name, sec)

            return result
        except Exception as e:
            ms = (time.time() - start) * 1000
            logger.error(f"Failed {node_name} node execution after {ms:.2f}ms: {e}")
            raise

    return cast(F, wrapper)


# ---------------------------------------------------------------------
# Agent creation + state<->context conversion
# ---------------------------------------------------------------------
async def create_agent_with_llm(agent_name: str) -> BaseAgent:
    registry = get_agent_registry()

    llm_config = OpenAIConfig.load()
    llm = OpenAIChatLLM(
        api_key=llm_config.api_key,
        model=llm_config.model,
        base_url=llm_config.base_url,
    )

    agent_config_kwargs: Dict[str, Any] = {}

    from OSSS.ai.config.agent_configs import HistorianConfig, RefinerConfig, CriticConfig, SynthesisConfig

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

    n = agent_name.lower()
    if n == "historian":
        agent_config_kwargs["config"] = HistorianConfig()
    elif n == "refiner":
        agent_config_kwargs["config"] = RefinerConfig()
    elif n == "critic":
        agent_config_kwargs["config"] = CriticConfig()
    elif n == "synthesis":
        agent_config_kwargs["config"] = SynthesisConfig()
    elif n == "guard" and GuardConfig is not None:
        agent_config_kwargs["config"] = GuardConfig()
    elif n == "data_views" and DataViewConfig is not None:
        agent_config_kwargs["config"] = DataViewConfig()

    raw_agent = registry.create_agent(n, llm=llm, **agent_config_kwargs)
    agent = await _coerce_base_agent(raw_agent, n)

    # preserve per-agent timeouts
    if n == "historian":
        agent.timeout_seconds = HistorianConfig().execution_config.timeout_seconds
    elif n == "refiner":
        agent.timeout_seconds = RefinerConfig().execution_config.timeout_seconds
    elif n == "critic":
        agent.timeout_seconds = CriticConfig().execution_config.timeout_seconds
    elif n == "synthesis":
        agent.timeout_seconds = SynthesisConfig().execution_config.timeout_seconds
    elif n == "guard" and GuardConfig is not None:
        agent.timeout_seconds = GuardConfig().execution_config.timeout_seconds
    elif n == "data_views" and DataViewConfig is not None:
        agent.timeout_seconds = DataViewConfig().execution_config.timeout_seconds

    return agent


async def convert_state_to_context(state: OSSSState) -> AgentContext:
    _ = AgentContextStateBridge()  # kept for compatibility/future use

    if "query" not in state:
        raise ValueError("State must contain a query field")

    context = AgentContext(query=cast(str, state.get("query", "")))

    exec_state = _ensure_exec_state_dict(state)
    # Make sure agent_output_meta exists + is threaded through
    context.execution_state["agent_output_meta"] = _get_agent_output_meta(state)

    # passthrough bits
    for k in ("effective_queries", "rag_context", "rag_hits", "rag_meta", "rag_enabled"):
        v = exec_state.get(k)
        if v is not None:
            context.execution_state[k] = v

    so = state.get("structured_outputs")
    if isinstance(so, dict):
        context.execution_state["structured_outputs"] = so

    # Optional: map known upstream outputs into AgentContext for agent convenience
    if isinstance(state.get("refiner"), dict):
        rq = cast(Dict[str, Any], state["refiner"]).get("refined_question")
        if isinstance(rq, str) and rq:
            context.add_agent_output("refiner", rq)
            context.add_agent_output("Refiner", rq)

    if isinstance(state.get("critic"), dict):
        cr = cast(Dict[str, Any], state["critic"]).get("critique")
        if isinstance(cr, str) and cr:
            context.add_agent_output("critic", cr)
            context.add_agent_output("Critic", cr)

    if isinstance(state.get("historian"), dict):
        hs = cast(Dict[str, Any], state["historian"]).get("historical_summary")
        if isinstance(hs, str) and hs:
            context.add_agent_output("historian", hs)
            context.add_agent_output("Historian", hs)

    if isinstance(state.get("synthesis"), dict):
        fa = cast(Dict[str, Any], state["synthesis"]).get("final_analysis")
        if isinstance(fa, str) and fa:
            context.add_agent_output("synthesis", fa)
            context.add_agent_output("Synthesis", fa)

    return context


# ---------------------------------------------------------------------
# Generic node runner (the main maintainability win)
# ---------------------------------------------------------------------
@dataclass(frozen=True)
class NodeSpec:
    node_name: str          # langgraph node name
    agent_name: str         # registry agent name
    state_key: str          # OSSSState field to populate (e.g. "critic")
    output_key: str         # AgentContext.agent_outputs key (e.g. "critic")
    requires: List[str]     # required state keys before executing (e.g. ["refiner"])
    # Compute effective query from (state, runtime)
    effective_query_fn: Optional[Callable[[OSSSState, Runtime[OSSSContext]], str]] = None
    # Build the typed state dict from AgentContext + raw output
    build_state_fn: Optional[Callable[[AgentContext, str, str], Any]] = None
    # Optional skip: return (skip, reason)
    skip_fn: Optional[Callable[[OSSSState, Runtime[OSSSContext]], Optional[str]]] = None
    # If agent missing, do we noop or fail?
    missing_agent_noop: bool = False


def _runtime_bits(runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    return {
        "thread_id": runtime.context.thread_id,
        "execution_id": runtime.context.execution_id,
        "query": runtime.context.query,
        "correlation_id": runtime.context.correlation_id,
        "checkpoint_enabled": runtime.context.enable_checkpoints,
        "emit_events": bool(getattr(runtime.context, "emit_events", False)),
    }


def _require(state: OSSSState, deps: List[str], node_name: str) -> None:
    for dep in deps:
        if not state.get(dep):
            raise NodeExecutionError(f"{node_name} node requires {dep} output")


def _default_effective_query(spec: NodeSpec, state: OSSSState, runtime: Runtime[OSSSContext]) -> str:
    # Prefer refined question if available; else original query; else state.query
    refined = ""
    if isinstance(state.get("refiner"), dict):
        refined = cast(Dict[str, Any], state["refiner"]).get("refined_question") or ""
    oq = runtime.context.query or ""
    q = state.get("query", "") or ""
    return refined or oq or cast(str, q)


async def _run_agent_node(spec: NodeSpec, state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    bits = _runtime_bits(runtime)
    thread_id = bits["thread_id"]
    execution_id = bits["execution_id"]
    correlation_id = bits["correlation_id"]
    original_query = bits["query"] or state.get("query", "")
    emit_events = bits["emit_events"]

    exec_state = _ensure_exec_state_dict(state)

    # dependency guard
    _require(state, spec.requires, spec.node_name)

    # optional skip hook
    if spec.skip_fn:
        reason = spec.skip_fn(state, runtime)
        if isinstance(reason, str) and reason:
            logger.info(f"Skipping {spec.node_name} node: {reason}")
            eff = (
                spec.effective_query_fn(state, runtime)
                if spec.effective_query_fn
                else _default_effective_query(spec, state, runtime)
            )
            _record_effective_query(state, spec.node_name, eff)
            # Do not mark as successful agent when skipped
            return {
                "execution_state": exec_state,
                spec.state_key: None,
                "successful_agents": state.get("successful_agents", []) or [],
                "structured_outputs": state.get("structured_outputs", {}) or {},
            }

    if emit_events:
        emit_agent_execution_started(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name=spec.agent_name,
            input_context={
                "query": original_query,
                "node_type": spec.node_name,
                "thread_id": thread_id,
                "execution_id": execution_id,
            },
            correlation_id=correlation_id,
            metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
        )

    try:
        try:
            agent = await create_agent_with_llm(spec.agent_name)
        except Exception as e:
            if not spec.missing_agent_noop:
                raise
            logger.warning(f"{spec.agent_name} agent not available; {spec.node_name} is a no-op: {e}")
            noop_payload = {"status": "skipped", "reason": "agent_not_registered", "timestamp": _now_iso()}
            exec_state[spec.state_key] = noop_payload
            state[spec.state_key] = noop_payload
            _merge_structured_outputs(state, {spec.state_key: noop_payload})
            return {
                "execution_state": exec_state,
                spec.state_key: noop_payload,
                "successful_agents": state.get("successful_agents", []) or [],
                "structured_outputs": state.get("structured_outputs", {}) or {},
            }

        context = await convert_state_to_context(state)

        eff = (
            spec.effective_query_fn(state, runtime)
            if spec.effective_query_fn
            else _default_effective_query(spec, state, runtime)
        )
        _record_effective_query(state, spec.node_name, eff)

        result_context = await agent.run_with_retry(context)
        raw_output = result_context.agent_outputs.get(spec.output_key, "") or ""

        # build typed state payload
        built = (
            spec.build_state_fn(result_context, raw_output, eff)
            if spec.build_state_fn
            else raw_output
        )

        structured_outputs = result_context.execution_state.get("structured_outputs", {})
        if isinstance(structured_outputs, dict) and structured_outputs:
            _merge_structured_outputs(state, structured_outputs)

        # legacy agent_outputs
        _set_agent_output(state, spec.node_name, built)
        _ensure_agent_outputs_nonempty(state, spec.node_name, str(raw_output or "ok"))

        # mark success (append)
        success_list = list(state.get("successful_agents") or []) if isinstance(state.get("successful_agents"), list) else []
        success_list.append(spec.node_name)

        if emit_events:
            token_usage = result_context.get_agent_token_usage(spec.output_key) if hasattr(result_context, "get_agent_token_usage") else {
                "input_tokens": 0, "output_tokens": 0, "total_tokens": 0
            }
            emit_agent_execution_completed(
                event_category=EventCategory.EXECUTION,
                workflow_id=execution_id,
                agent_name=spec.agent_name,
                success=True,
                output_context={
                    "node_type": spec.node_name,
                    "thread_id": thread_id,
                    "execution_id": execution_id,
                    "input_tokens": token_usage.get("input_tokens", 0),
                    "output_tokens": token_usage.get("output_tokens", 0),
                    "total_tokens": token_usage.get("total_tokens", 0),
                },
                correlation_id=correlation_id,
                metadata={"node_execution": True, "orchestrator_type": "langgraph-real", "token_usage": token_usage},
            )

        return {
            "execution_state": exec_state,
            spec.state_key: built,
            "successful_agents": success_list,
            "structured_outputs": state.get("structured_outputs", {}) or {},
        }

    except Exception as e:
        if emit_events:
            emit_agent_execution_completed(
                event_category=EventCategory.EXECUTION,
                workflow_id=execution_id,
                agent_name=spec.agent_name,
                success=False,
                output_context={"error": str(e), "node_type": spec.node_name, "thread_id": thread_id, "execution_id": execution_id},
                error_message=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
                metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
            )
        record_agent_error(state, spec.node_name, e)
        raise NodeExecutionError(f"{spec.node_name} execution failed: {e}") from e


# ---------------------------------------------------------------------
# Node-specific builders / skip hooks
# ---------------------------------------------------------------------
def _build_refiner_state(ctx: AgentContext, raw: str, eff: str) -> RefinerState:
    return RefinerState(
        refined_question=raw,
        topics=ctx.execution_state.get("topics", []),
        confidence=ctx.execution_state.get("confidence", 0.8),
        processing_notes=ctx.execution_state.get("processing_notes"),
        timestamp=_now_iso(),
        agent_output_meta=ctx.execution_state.get("agent_output_meta", {}),
    )


def _build_critic_state(ctx: AgentContext, raw: str, eff: str) -> CriticState:
    return CriticState(
        critique=raw,
        suggestions=ctx.execution_state.get("suggestions", []),
        severity=ctx.execution_state.get("severity", "medium"),
        strengths=ctx.execution_state.get("strengths", []),
        weaknesses=ctx.execution_state.get("weaknesses", []),
        confidence=ctx.execution_state.get("confidence", 0.7),
        timestamp=_now_iso(),
        agent_output_meta=ctx.execution_state.get("agent_output_meta", {}),
    )


def _build_historian_state(ctx: AgentContext, raw: str, eff: str) -> HistorianState:
    retrieved_notes = getattr(ctx, "retrieved_notes", [])
    topics_found = ctx.execution_state.get("topics_found", [])
    return HistorianState(
        historical_summary=raw,
        retrieved_notes=retrieved_notes,
        search_results_count=ctx.execution_state.get("search_results_count", 0),
        filtered_results_count=ctx.execution_state.get("filtered_results_count", 0),
        search_strategy=ctx.execution_state.get("search_strategy", "hybrid"),
        topics_found=topics_found,
        confidence=ctx.execution_state.get("confidence", 0.8),
        llm_analysis_used=ctx.execution_state.get("llm_analysis_used", True),
        metadata=ctx.execution_state.get("historian_metadata", {}),
        timestamp=_now_iso(),
        agent_output_meta=ctx.execution_state.get("agent_output_meta", {}),
    )


def _build_synthesis_state(ctx: AgentContext, raw: str, eff: str) -> SynthesisState:
    # infer sources_used from state written into AgentContext (best-effort)
    sources_used: List[str] = []
    for k in ("refiner", "critic", "historian"):
        if ctx.agent_outputs.get(k):
            sources_used.append(k)
    return SynthesisState(
        final_analysis=raw,
        key_insights=ctx.execution_state.get("key_insights", []),
        sources_used=sources_used,
        themes_identified=ctx.execution_state.get("themes", []),
        conflicts_resolved=ctx.execution_state.get("conflicts_resolved", 0),
        confidence=ctx.execution_state.get("confidence", 0.8),
        metadata=ctx.execution_state.get("synthesis_metadata", {}),
        timestamp=_now_iso(),
        agent_output_meta=ctx.execution_state.get("agent_output_meta", {}),
    )


def _skip_historian(state: OSSSState, runtime: Runtime[OSSSContext]) -> Optional[str]:
    oq = runtime.context.query or cast(str, state.get("query", ""))
    return "routing_heuristic" if not should_run_historian(oq) else None


# ---------------------------------------------------------------------
# Node Specs
# ---------------------------------------------------------------------
REFINER_SPEC = NodeSpec(
    node_name="refiner",
    agent_name="refiner",
    state_key="refiner",
    output_key="refiner",
    requires=[],
    build_state_fn=_build_refiner_state,
)

CRITIC_SPEC = NodeSpec(
    node_name="critic",
    agent_name="critic",
    state_key="critic",
    output_key="critic",
    requires=["refiner"],
    build_state_fn=_build_critic_state,
)

HISTORIAN_SPEC = NodeSpec(
    node_name="historian",
    agent_name="historian",
    state_key="historian",
    output_key="historian",
    requires=["refiner"],
    build_state_fn=_build_historian_state,
    skip_fn=_skip_historian,
)

SYNTHESIS_SPEC = NodeSpec(
    node_name="synthesis",
    agent_name="synthesis",
    state_key="synthesis",
    output_key="synthesis",
    requires=["refiner", "critic"],  # historian optional, enforced in node below
    build_state_fn=_build_synthesis_state,
)


# ---------------------------------------------------------------------
# Public nodes (thin wrappers around _run_agent_node)
# ---------------------------------------------------------------------
@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def refiner_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    return await _run_agent_node(REFINER_SPEC, state, runtime)


@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def critic_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    return await _run_agent_node(CRITIC_SPEC, state, runtime)


@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def historian_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    return await _run_agent_node(HISTORIAN_SPEC, state, runtime)


@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def synthesis_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    # enforce historian requirement only when heuristic says it should have run
    oq = runtime.context.query or cast(str, state.get("query", ""))
    if should_run_historian(oq) and not state.get("historian"):
        raise NodeExecutionError("Synthesis node requires historian output for this query")
    return await _run_agent_node(SYNTHESIS_SPEC, state, runtime)


# ---------------------------------------------------------------------
# Guard pipeline nodes (kept explicit, but still using shared helpers)
# ---------------------------------------------------------------------
@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def guard_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    bits = _runtime_bits(runtime)
    thread_id = bits["thread_id"]
    execution_id = bits["execution_id"]
    correlation_id = bits["correlation_id"]
    emit_events = bits["emit_events"]
    original_query = bits["query"] or state.get("query", "")

    exec_state = _ensure_exec_state_dict(state)
    _record_effective_query(state, "guard", str(original_query))

    if emit_events:
        emit_agent_execution_started(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name="guard",
            input_context={"query": original_query, "thread_id": thread_id, "execution_id": execution_id},
            correlation_id=correlation_id,
            metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
        )

    try:
        try:
            agent = await create_agent_with_llm("guard")
        except Exception as e:
            msg = f"Guard not configured; passed through query unchanged. ({type(e).__name__})"
            logger.warning(f"Guard agent not available; guard_node is a no-op: {e}")
            payload: Dict[str, Any] = {
                "allowed": True,
                "decision": "allow",
                "action": "noop",
                "reason": "agent_unavailable",
                "message": msg,
                "timestamp": _now_iso(),
            }
            exec_state["guard"] = payload
            state["guard"] = payload
            _set_guard_decision(state, "allow")
            _merge_structured_outputs(state, {"guard": payload})

            _set_agent_output(state, "guard", payload)
            _ensure_agent_outputs_nonempty(state, "guard", msg)

            success = list(state.get("successful_agents") or []) if isinstance(state.get("successful_agents"), list) else []
            success.append("guard")

            if emit_events:
                emit_agent_execution_completed(
                    event_category=EventCategory.EXECUTION,
                    workflow_id=execution_id,
                    agent_name="guard",
                    success=True,
                    output_context={"allowed": True, "action": "noop", "thread_id": thread_id, "execution_id": execution_id},
                    correlation_id=correlation_id,
                    metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
                )
            return {"execution_state": exec_state, "guard": payload, "guard_decision": state.get("guard_decision"), "successful_agents": success}

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
            decision = "allow" if raw_payload.get("allowed") is not False else "block"

        payload = {
            "allowed": bool(raw_payload.get("allowed", True)),
            "decision": str(decision),
            "action": str(raw_payload.get("action", "guard")),
            "reason": str(raw_payload.get("reason", "")),
            "message": str(raw_payload.get("message", guard_output)),
            "timestamp": _now_iso(),
        }

        exec_state["guard"] = payload
        state["guard"] = payload
        _set_guard_decision(state, decision)
        _merge_structured_outputs(state, {"guard": payload})

        _set_agent_output(state, "guard", payload)
        _ensure_agent_outputs_nonempty(state, "guard", payload["message"] or guard_output)

        success = list(state.get("successful_agents") or []) if isinstance(state.get("successful_agents"), list) else []
        success.append("guard")

        if emit_events:
            emit_agent_execution_completed(
                event_category=EventCategory.EXECUTION,
                workflow_id=execution_id,
                agent_name="guard",
                success=True,
                output_context={"message": truncate_for_websocket_event(payload["message"], "guard"), "thread_id": thread_id},
                correlation_id=correlation_id,
                metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
            )

        return {
            "execution_state": exec_state,
            "guard": payload,
            "guard_decision": state.get("guard_decision"),
            "successful_agents": success,
            "structured_outputs": state.get("structured_outputs", {}) or {},
        }

    except Exception as e:
        if emit_events:
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
    bits = _runtime_bits(runtime)
    thread_id = bits["thread_id"]
    execution_id = bits["execution_id"]
    correlation_id = bits["correlation_id"]
    emit_events = bits["emit_events"]
    original_query = bits["query"] or state.get("query", "")

    exec_state = _ensure_exec_state_dict(state)
    _record_effective_query(state, "answer_search", str(original_query))

    if emit_events:
        emit_agent_execution_started(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name="answer_search",
            input_context={"query": original_query, "thread_id": thread_id, "execution_id": execution_id},
            correlation_id=correlation_id,
            metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
        )

    try:
        try:
            agent = await create_agent_with_llm("answer_search")
        except Exception as e:
            logger.warning(f"answer_search agent not available; falling back: {e}")

            syn = state.get("synthesis") or {}
            fallback_answer = syn.get("final_analysis", "") if isinstance(syn, dict) else ""
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

            success = list(state.get("successful_agents") or []) if isinstance(state.get("successful_agents"), list) else []
            success.append("answer_search")

            if emit_events:
                emit_agent_execution_completed(
                    event_category=EventCategory.EXECUTION,
                    workflow_id=execution_id,
                    agent_name="answer_search",
                    success=True,
                    output_context={"fallback": True, "thread_id": thread_id, "execution_id": execution_id},
                    correlation_id=correlation_id,
                    metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
                )

            return {"execution_state": exec_state, "answer_search": payload, "successful_agents": success}

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
        _ensure_agent_outputs_nonempty(state, "answer_search", str(payload.get("answer_text") or raw or "ok"))

        success = list(state.get("successful_agents") or []) if isinstance(state.get("successful_agents"), list) else []
        success.append("answer_search")

        if emit_events:
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
            "successful_agents": success,
            "structured_outputs": state.get("structured_outputs", {}) or {},
        }

    except Exception as e:
        if emit_events:
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
    exec_state = _ensure_exec_state_dict(state)

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
    state["ui_response"] = ui
    _merge_structured_outputs(state, {"final_response": ui})

    _set_agent_output(state, "format_response", ui)
    _ensure_agent_outputs_nonempty(state, "format_response", str(ui.get("message") or "ok"))

    success = list(state.get("successful_agents") or []) if isinstance(state.get("successful_agents"), list) else []
    success.append("format_response")

    return {
        "execution_state": exec_state,
        "final_response": ui,
        "successful_agents": success,
        "structured_outputs": state.get("structured_outputs", {}) or {},
    }


@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def format_block_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    exec_state = _ensure_exec_state_dict(state)
    guard_payload = state.get("guard") or exec_state.get("guard") or {}
    msg = "Sorry, I can’t help with that request."
    if isinstance(guard_payload, dict):
        msg = str(guard_payload.get("safe_response") or guard_payload.get("message") or guard_payload.get("reason") or msg)

    ui: Dict[str, Any] = {"status": "blocked", "message": msg, "sources": [], "timestamp": _now_iso()}
    exec_state["format_block"] = {"ui": ui}
    exec_state["final_response"] = ui
    state["final_response"] = ui
    state["ui_response"] = ui
    _merge_structured_outputs(state, {"final_response": ui})

    _set_agent_output(state, "format_block", ui)
    _ensure_agent_outputs_nonempty(state, "format_block", msg)

    success = list(state.get("successful_agents") or []) if isinstance(state.get("successful_agents"), list) else []
    success.append("format_block")

    return {"execution_state": exec_state, "final_response": ui, "successful_agents": success}


@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def format_requires_confirmation_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    exec_state = _ensure_exec_state_dict(state)
    guard_payload = state.get("guard") or exec_state.get("guard") or {}
    msg = "This request requires confirmation to proceed."
    if isinstance(guard_payload, dict):
        msg = str(guard_payload.get("reason") or guard_payload.get("message") or msg)

    ui: Dict[str, Any] = {"status": "requires_confirmation", "message": msg, "sources": [], "timestamp": _now_iso()}
    exec_state["format_requires_confirmation"] = {"ui": ui}
    exec_state["final_response"] = ui
    state["final_response"] = ui
    state["ui_response"] = ui
    _merge_structured_outputs(state, {"final_response": ui})

    _set_agent_output(state, "format_requires_confirmation", ui)
    _ensure_agent_outputs_nonempty(state, "format_requires_confirmation", msg)

    success = list(state.get("successful_agents") or []) if isinstance(state.get("successful_agents"), list) else []
    success.append("format_requires_confirmation")

    return {"execution_state": exec_state, "final_response": ui, "successful_agents": success}


# ---------------------------------------------------------------------
# Data views node (Option B) - uses meta helpers
# ---------------------------------------------------------------------
@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def data_view_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    bits = _runtime_bits(runtime)
    thread_id = bits["thread_id"]
    execution_id = bits["execution_id"]
    correlation_id = bits["correlation_id"]
    emit_events = bits["emit_events"]
    original_query = bits["query"] or state.get("query", "")

    exec_state = _ensure_exec_state_dict(state)

    if emit_events:
        emit_agent_execution_started(
            event_category=EventCategory.EXECUTION,
            workflow_id=execution_id,
            agent_name="data_views",
            input_context={"query": original_query, "node_type": "data_views", "thread_id": thread_id, "execution_id": execution_id},
            correlation_id=correlation_id,
            metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
        )

    try:
        try:
            agent = await create_agent_with_llm("data_views")
        except Exception as e:
            logger.warning(f"DataView agent not available; data_view_node is a no-op: {e}")
            dv = {"status": "skipped", "reason": "agent_not_registered", "timestamp": _now_iso()}
            exec_state["data_views"] = dv
            state["data_views"] = dv
            _merge_structured_outputs(state, {"data_views": dv})
            return {"execution_state": exec_state, "data_views": dv, "successful_agents": state.get("successful_agents", []) or []}

        context = await convert_state_to_context(state)

        # effective query: refined > original > state.query
        refined = ""
        if isinstance(state.get("refiner"), dict):
            refined = cast(Dict[str, Any], state["refiner"]).get("refined_question") or ""
        eff = refined or (bits["query"] or state.get("query", "") or context.query)
        _record_effective_query(state, "data_views", str(eff))

        # Pull orchestrator meta
        query_profile = _get_query_profile(state)
        routing_decision = _get_routing_meta(state)

        synthesis_state = _first_present(state, "synthesis")
        answer_state = _first_present(state, "answer_search")

        if isinstance(synthesis_state, dict) and synthesis_state.get("final_analysis"):
            dv_input = {"source": "synthesis", "input": synthesis_state.get("final_analysis"), "query": eff,
                        "query_profile": query_profile, "routing_decision": routing_decision}
        elif isinstance(answer_state, dict) and (answer_state.get("answer_text") or answer_state.get("sources") is not None):
            dv_input = {"source": "answer_search", "input": answer_state.get("answer_text") or "", "sources": answer_state.get("sources") or [],
                        "query": eff, "query_profile": query_profile, "routing_decision": routing_decision}
        else:
            dv_input = {"source": "raw", "input": {"query": eff, "query_profile": query_profile, "routing_decision": routing_decision},
                        "query": eff, "query_profile": query_profile, "routing_decision": routing_decision}

        context.execution_state["data_view_input"] = dv_input

        result_context = await agent.run_with_retry(context)
        raw = result_context.agent_outputs.get("data_views", "")

        payload = result_context.execution_state.get("data_view_payload")
        if payload is None:
            payload = result_context.execution_state.get("structured_outputs")

        dv_state: Dict[str, Any] = {
            "payload": payload,
            "raw": truncate_for_websocket_event(str(raw), "data_views"),
            "input_source": dv_input.get("source"),
            "timestamp": _now_iso(),
        }

        exec_state["data_views"] = dv_state
        state["data_views"] = dv_state
        _merge_structured_outputs(state, {"data_views": dv_state})

        _set_agent_output(state, "data_views", dv_state)
        _ensure_agent_outputs_nonempty(state, "data_views", str(dv_state.get("raw") or "ok"))

        success = list(state.get("successful_agents") or []) if isinstance(state.get("successful_agents"), list) else []
        success.append("data_views")

        if emit_events:
            token_usage = result_context.get_agent_token_usage("data_views")
            emit_agent_execution_completed(
                event_category=EventCategory.EXECUTION,
                workflow_id=execution_id,
                agent_name="data_views",
                success=True,
                output_context={"thread_id": thread_id, "execution_id": execution_id, "has_payload": bool(payload), "input_source": dv_input.get("source")},
                correlation_id=correlation_id,
                metadata={"node_execution": True, "orchestrator_type": "langgraph-real", "token_usage": token_usage},
            )

        return {"execution_state": exec_state, "data_views": dv_state, "successful_agents": success}

    except Exception as e:
        if emit_events:
            emit_agent_execution_completed(
                event_category=EventCategory.EXECUTION,
                workflow_id=execution_id,
                agent_name="data_views",
                success=False,
                output_context={"error": str(e), "thread_id": thread_id, "execution_id": execution_id},
                error_message=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
                metadata={"node_execution": True, "orchestrator_type": "langgraph-real"},
            )
        record_agent_error(state, "data_views", e)
        raise NodeExecutionError(f"DataView execution failed: {e}") from e


# ---------------------------------------------------------------------
# Timeout helper
# ---------------------------------------------------------------------
async def handle_node_timeout(coro: Coroutine[Any, Any, Any], timeout_seconds: float = 30.0) -> Any:
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise NodeExecutionError(f"Node execution timed out after {timeout_seconds}s")


# ---------------------------------------------------------------------
# Dependencies (Option B)
# ---------------------------------------------------------------------
def get_node_dependencies() -> Dict[str, List[str]]:
    return {
        "guard": [],
        "answer_search": ["guard"],
        "format_response": ["answer_search"],
        "format_block": ["guard"],
        "format_requires_confirmation": ["guard"],
        "refiner": [],
        "critic": ["refiner"],
        "historian": ["refiner"],
        "synthesis": ["critic"],  # historian optional, enforced in synthesis_node
        "data_views": [],  # Option B: no hard deps
    }


def validate_node_input(state: OSSSState, node_name: str) -> bool:
    deps = get_node_dependencies().get(node_name, [])
    missing = [d for d in deps if not state.get(d)]
    for d in missing:
        logger.warning(f"Node {node_name} missing required dependency: {d}")
    return not missing



__all__ = [
    "guard_node",
    "answer_search_node",
    "format_response_node",
    "format_block_node",
    "data_view_node",
    "format_requires_confirmation_node",
    "refiner_node",
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
    # helpers (optional)
    "get_timing_registry",
    "clear_timing_registry",
]
