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
    FinalState,
    record_agent_error,
)
from OSSS.ai.rag.additional_index_rag import rag_prefetch_additional

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

async def _ensure_rag_for_final(
    *,
    state: OSSSState,
    runtime: Runtime[OSSSContext],
    exec_state: Dict[str, Any],
) -> None:
    """
    Best-effort RAG hydration for final_node.

    If RAG is enabled in the execution config or we already ran prefetch earlier
    in the workflow, make sure exec_state['rag_context'] is populated.
    """

    # 🔹 Use the same config resolver used elsewhere so fastpath runs see use_rag
    ec = _get_execution_config(state, runtime)
    if not isinstance(ec, dict):
        ec = {}
    exec_state["execution_config"] = ec

    rag_cfg = ec.get("rag")
    if not isinstance(rag_cfg, dict):
        rag_cfg = {}

    # 🔹 Derive "rag_enabled" in a tolerant way
    rag_enabled = bool(
        rag_cfg.get("enabled")
        or ec.get("use_rag")                  # from API raw_execution_config
        or exec_state.get("rag_enabled")      # maybe set by other nodes/routes
        or state.get("rag_context")           # if orchestrator already injected context
    )

    if not rag_enabled:
        exec_state["rag_enabled"] = False
        return

    # 🔹 If orchestrator already injected rag_context into state, just adopt it.
    existing_ctx = exec_state.get("rag_context") or state.get("rag_context")
    if isinstance(existing_ctx, str) and existing_ctx.strip():
        exec_state["rag_context"] = existing_ctx
        exec_state["rag_enabled"] = True
        return

    # Build the query we'll embed against
    user_question = (
        exec_state.get("user_question")
        or state.get("query")
        or state.get("original_query")
        or runtime.context.query
        or ""
    ).strip()

    if not user_question:
        # Nothing sensible to embed
        exec_state["rag_enabled"] = False
        return

    index = rag_cfg.get("index", "main")
    top_k = int(rag_cfg.get("top_k", 5))
    embed_model = rag_cfg.get("embed_model", "nomic-embed-text")

    logger.info(
        "[final_node] RAG context missing; performing on-demand prefetch",
        extra={
            "index": index,
            "top_k": top_k,
            "embed_model": embed_model,
            "query_preview": user_question[:80],
        },
    )

    try:
        rag_context = await rag_prefetch_additional(
            query=user_question,
            index=index,
            top_k=top_k,
        )

        rag_context = rag_context or ""
        exec_state["rag_context"] = rag_context
        exec_state.setdefault("rag_hits", [])
        exec_state["rag_enabled"] = bool(rag_context.strip())
        exec_state["rag_meta"] = {
            "provider": "ollama",
            "embed_model": embed_model,
            "index": index,
            "top_k": top_k,
        }

        logger.info(
            "[final_node] RAG prefetch completed",
            extra={
                "index": index,
                "top_k": top_k,
                "rag_chars": len(rag_context),
            },
        )
    except Exception as e:
        logger.warning(
            f"[final_node] RAG prefetch failed (continuing without RAG): {e}"
        )
        exec_state["rag_enabled"] = False
        exec_state.setdefault("rag_error", str(e))


def extract_question_from_refiner(markdown: str) -> str | None:
    # Try to find the `* **Query**: ...` line
    for line in markdown.splitlines():
        line = line.strip()
        if line.startswith("* **Query**:"):
            return line.split(":", 1)[1].strip()
    return None

def _canon_agent_key(name: str) -> str:
    return (name or "").strip().lower().replace("-", "_")


def _ensure_exec_state(state: Dict[str, Any]) -> Dict[str, Any]:
    exec_state = state.get("execution_state")
    if not isinstance(exec_state, dict):
        exec_state = {}
        state["execution_state"] = exec_state
    return exec_state


def _ensure_execution_config(exec_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure exec_state["execution_config"] exists and is a dict.
    """
    ec = exec_state.get("execution_config")
    if not isinstance(ec, dict):
        ec = {}
        exec_state["execution_config"] = ec
    return ec


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


# ---------------------------------------------------------------------------
# Planning helpers (Option A)
# ---------------------------------------------------------------------------

def apply_option_a_fastpath_planning(
    *,
    exec_state: Dict[str, Any],
    chosen_target: str,
) -> None:
    """
    Option A: planning belongs outside LangGraph nodes.

    This helper is intended to be called by the planner/optimizer/GraphFactory
    BEFORE graph compilation (i.e., before nodes/edges are decided).

    Behavior:
      - If caller did not explicitly set a graph_pattern, and the route is informational
        (chosen_target != "data_query"), force the fastpath:
          graph_pattern = "refiner_final"
          planned_agents = ["refiner", "final"]
      - Otherwise, default graph_pattern to "standard" if still unset.

    NOTE:
      - This is intentionally *not* invoked from route_gate_node.
      - If you support route locking, the planner should decide how/when to respect it.
    """
    ec = _ensure_execution_config(exec_state)

    # Respect existing caller override if provided
    if isinstance(ec.get("graph_pattern"), str) and ec.get("graph_pattern"):
        return

    if chosen_target != "data_query":
        ec["graph_pattern"] = "refiner_final"
        exec_state["planned_agents"] = ["refiner", "final"]
    else:
        ec.setdefault("graph_pattern", "standard")


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

        model_path = classifier_cfg.get("model_path", "models/domain_topic_intent_classifier.joblib")
        model_version = classifier_cfg.get("model_version", "v1")

        logger.info(
            "Creating classifier agent",
            extra={"agent_name": "classifier", "model_path": str(model_path), "model_version": model_version},
        )
        return registry.create_agent(agent_name_lower, model_path=model_path, model_version=model_version)

    if agent_name_lower == "data_query":
        return registry.create_agent(agent_name_lower)

    # Option A: "output" is a pure LangGraph node and NOT a BaseAgent.
    # We intentionally do not create an "output" agent here.

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
    # Prefer explicitly stored original_query if present
    original_query = (state.get("original_query") or "").strip() or query

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
            # ✅ keep execution_config/planned_agents flowing through
            "execution_config",
            "planned_agents",
            "route_key",
            "route",
            "route_reason",
            "route_locked",
        ):
            v = state_exec.get(k)
            if v is not None:
                context.execution_state[k] = v

        # ✅ propagate full refiner text if present so downstream agents / API can use it
        refiner_full = state_exec.get("refiner_full_text")
        if isinstance(refiner_full, str) and refiner_full.strip():
            context.execution_state["refiner_full_text"] = refiner_full

    # 🔧 NEW: also allow RAG to come from top-level state if orchestrator
    # injected it there before running the graph.
    for k in ("rag_context", "rag_snippet", "rag_hits", "rag_meta"):
        if k not in context.execution_state and k in state:
            v = state.get(k)
            if v is not None:
                context.execution_state[k] = v


    # ✅ Make sure FinalAgent has something to treat as the user question
    # user_question: what we show to the FINAL agent
    context.execution_state.setdefault("original_query", original_query)
    context.execution_state.setdefault("user_question", original_query)

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

                # ✅ Provide refiner_snippet for FinalAgent:
                # prefer the full markdown text if we have it, fall back to the refined question
                refiner_full = context.execution_state.get("refiner_full_text")
                if isinstance(refiner_full, str) and refiner_full.strip():
                    snippet = refiner_full
                else:
                    snippet = refined_question
                if snippet.strip():
                    context.execution_state.setdefault("refiner_snippet", snippet)

    # ✅ Derive rag_snippet from rag_context when available
    rag_ctx = context.execution_state.get("rag_context")
    if rag_ctx is not None and not context.execution_state.get("rag_snippet"):
        rag_snippet = _to_text(rag_ctx)
        if rag_snippet.strip():
            context.execution_state["rag_snippet"] = rag_snippet

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
                "successful_agents": state.get("successful_agents", []).copy()
                if isinstance(state.get("successful_agents"), list)
                else [],
                "failed_agents": state.get("failed_agents", []).copy()
                if isinstance(state.get("failed_agents"), list)
                else [],
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

    # Read config for logging only (do NOT mutate planning here; Option A)
    ec = exec_state.get("execution_config", {}) if isinstance(exec_state.get("execution_config"), dict) else {}

    logger.info(
        "Route chosen",
        extra={
            "graph_pattern": ec.get("graph_pattern"),
            "planned_agents": exec_state.get("planned_agents"),
        },
    )

    # Option A: you can keep this; it's harmless even if only some agents use it.
    exec_state["rag_enabled"] = True

    # Option A: planning/fastpath selection happens BEFORE compilation (planner/GraphFactory).
    # route_gate_node must not mutate graph_pattern/planned_agents because it's too late.
    ec = _ensure_execution_config(exec_state)

    aom = exec_state.setdefault("agent_output_meta", {})
    if isinstance(aom, dict):
        routing = aom.setdefault("_routing", {})
        if isinstance(routing, dict):
            routing["source"] = "route_gate"
            routing["planned_agents"] = list(exec_state.get("planned_agents") or [])
            routing["route_key"] = route_key
            routing["chosen_target"] = chosen_target
            routing["graph_pattern"] = ec.get("graph_pattern")

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
                "graph_pattern": ec.get("graph_pattern"),
                "planned_agents": exec_state.get("planned_agents"),
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
            "graph_pattern": ec.get("graph_pattern"),
            "planned_agents": exec_state.get("planned_agents"),
            "route_reason": exec_state.get("route_reason"),
        },
    )

    state_original = state.get("original_query")
    prev_query = state.get("query", "") or ""
    original_for_state = state_original or prev_query or (original_query or "")

    return {
        "execution_state": exec_state,
        "route_key": route_key,
        "route": chosen_target,
        "original_query": original_for_state,
    }


# ---------------------------------------------------------------------------
# Node wrappers
# ---------------------------------------------------------------------------
@circuit_breaker(max_failures=3, reset_timeout=300.0)
@node_metrics
async def final_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    thread_id = runtime.context.thread_id
    execution_id = runtime.context.execution_id
    correlation_id = runtime.context.correlation_id

    logger.info(
        f"Executing final node in thread {thread_id}",
        extra={
            "thread_id": thread_id,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
        },
    )

    try:
        # Run the real "final" agent (LLM-backed)
        agent = await create_agent_with_llm("final", state=state, runtime=runtime)
        context = await convert_state_to_context(state)

        # 🔧 Merge AgentContext.execution_state into the graph's execution_state
        # so we have ONE source of truth that will be written back to LangGraph.
        graph_exec_state = _ensure_exec_state(state)
        if isinstance(context.execution_state, dict):
            graph_exec_state.update(context.execution_state)

        exec_state = graph_exec_state

        # 1) user_question: prefer promoted query, then runtime.context.query
        if not exec_state.get("user_question"):
            uq = (
                (state.get("query") or "")              # promoted/refined query in graph state
                or (state.get("original_query") or "")  # preserved original
                or (runtime.context.query or "")        # raw API query
                or context.query                        # AgentContext fallback
            )
            if uq:
                exec_state["user_question"] = uq

        # 2) refiner_snippet: try refined_question from refiner_state or full markdown
        if not exec_state.get("refiner_snippet"):
            refined_question = ""
            refiner_state = state.get("refiner")
            if isinstance(refiner_state, dict):
                refined_question = (refiner_state.get("refined_question") or "").strip()

            # if you later store full markdown, you can prefer that:
            refiner_full = (exec_state.get("refiner_full_text") or "").strip()
            snippet_source = refiner_full or refined_question

            if snippet_source:
                exec_state["refiner_snippet"] = snippet_source

        # 3) 🔥 RAG SNIPPET: bridge orchestrator's rag_context -> what FinalAgent expects
        await _ensure_rag_for_final(state=state, runtime=runtime, exec_state=exec_state)

        if not exec_state.get("rag_snippet"):
            rag_ctx = (
                    exec_state.get("rag_context")
                    or state.get("rag_context")
            )

            if isinstance(rag_ctx, str) and rag_ctx.strip():
                exec_state["rag_snippet"] = rag_ctx.strip()
                logger.debug(
                    "[final_node] Set rag_snippet from rag_context (first 100 chars): %s",
                    rag_ctx[:100],
                )
            else:
                logger.warning(
                    "[final_node] rag_context is missing or empty after _ensure_rag_for_final; "
                    "rag_snippet not set."
                )

        # (Optional but handy) log what we're about to send to FINAL
        logger.info(
            "[final_node] Prepared context for FinalAgent",
            extra={
                "user_question_preview": (exec_state.get("user_question") or "")[:120],
                "refiner_snippet_present": bool(exec_state.get("refiner_snippet")),
                "rag_snippet_present": bool(exec_state.get("rag_snippet")),
            },
        )

        # ✅ make sure the Final agent actually sees the unified execution state
        context.execution_state = exec_state

        effective_query = runtime.context.query or state.get("query", "") or context.query
        _record_effective_query(state, "final", effective_query)

        result_context = await agent.run_with_retry(context)

        final_text = (result_context.agent_outputs.get("final") or "").strip()
        if not final_text:
            # fail loudly so you notice misconfiguration
            raise NodeExecutionError("Final agent ran but produced no 'final' output")

        state["final"] = FinalState(
            final_answer=final_text,
            used_rag=bool(state.get("rag_snippet")),
            rag_excerpt=(state.get("rag_snippet") or "")[:500] or None,
            sources_used=["refiner"] + (["historian"] if state.get("historian") else []),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        structured = state.get("structured_outputs")
        if not isinstance(structured, dict):
            structured = {}
        structured["final"] = final_text

        succ = state.get("successful_agents")
        if not isinstance(succ, list):
            succ = []
        if "final" not in succ:
            succ.append("final")

        # exec_state already points at the graph's execution_state dict
        return {
            "execution_state": exec_state,
            "structured_outputs": structured,
            "successful_agents": succ,
            "final_output": final_text,
        }

    except Exception as e:
        record_agent_error(state, "final", e)
        raise NodeExecutionError(f"Final execution failed: {e}") from e

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

        result_context = await agent.run_with_retry(context)

        # Full raw text from the LLM
        refiner_raw_output = (result_context.agent_outputs.get("refiner") or "").strip()

        # Canonicalized refined question
        refined_question = canonicalize_dcg(extract_refined_question(refiner_raw_output))

        # ✅ Ensure we have execution_state before we mutate it
        exec_state = _ensure_exec_state(state)

        # ✅ Preserve full refiner text once for downstream consumers (FinalAgent, API, markdown)
        if isinstance(refiner_raw_output, str) and refiner_raw_output.strip():
            exec_state.setdefault("refiner_full_text", refiner_raw_output)

        # ✅ Guardrail: if canonicalization produced junk (e.g., just "**" or a tiny heading),
        # fall back to the full raw output so we don't lose information.
        if isinstance(refined_question, str):
            rq_stripped = refined_question.strip()
            if (
                not rq_stripped
                or not any(ch.isalnum() for ch in rq_stripped)
                or (len(rq_stripped) < 8 and len(refiner_raw_output) > len(rq_stripped) * 2)
            ):
                refined_question = refiner_raw_output

        # Preserve original query exactly once (first writer wins)
        prev_query = (state.get("query") or "").strip()
        state_original = (state.get("original_query") or "").strip()
        runtime_original = (original_query or "").strip()

        original_for_state = state_original or prev_query or runtime_original
        promoted_query = (refined_question or "").strip() or prev_query or runtime_original

        refiner_state = RefinerState(
            refined_question=refined_question,
            topics=result_context.execution_state.get("topics", []),
            confidence=result_context.execution_state.get("confidence", 0.8),
            processing_notes=result_context.execution_state.get("processing_notes"),
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_output_meta=result_context.execution_state.get("agent_output_meta", {}),
        )

        structured_outputs = result_context.execution_state.get("structured_outputs", {})

        return {
            "execution_state": exec_state,
            "original_query": original_for_state,
            "query": promoted_query,
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

        payload: Any = None
        if isinstance(getattr(result_context, "execution_state", None), dict):
            payload = result_context.execution_state.get("data_query_result")
            if payload is None:
                payload = dq_value

            if "data_view" not in result_context.execution_state and payload is not None:
                result_context.execution_state["data_view"] = payload
        else:
            payload = dq_value

        canonical_value = payload if payload is not None else ""

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

        option_a_updates: Dict[str, Any] = {
            "completed_data_query_nodes": [dq_node_id],
            "data_query_results": {dq_node_id: canonical_value},
        }

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

        effective_query = (state.get("query", "") or "").strip() or refined or (original_query or "") or context.query
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

        effective_query = (state.get("query", "") or "").strip() or refined or (original_query or "")
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

        effective_query = (state.get("query", "") or "").strip() or refined or (original_query or "") or context.query
        _record_effective_query(state, "historian", effective_query)

        result_context = await agent.run_with_retry(context)

        historian_raw_output = result_context.agent_outputs.get("historian", "")
        retrieved_notes = getattr(result_context, "retrieved_notes", [])
        topics_found = (
            result_context.execution_state.get("topics_found", [])
            if isinstance(result_context.execution_state, dict)
            else []
        )

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
    (Kept for compatibility; if you switch patterns to terminate at output, synthesis may not run.)
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

        dq_payload = _pick_latest_data_query_payload(state)
        data_query_text = _to_text(dq_payload) if dq_payload is not None else ""

        if data_query_text:
            mode = "action"
        elif critic_text or historian_text:
            mode = "reflection"
        else:
            mode = "fallback"

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

        effective_query = (state.get("query", "") or "").strip() or refined or (original_query or "") or context.query
        _record_effective_query(state, "synthesis", effective_query)

        synthesis_raw_output = ""

        if mode == "action":
            synthesis_raw_output = data_query_text
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
        # Option A: output is a terminal node; keep refiner dep for the fastpath pattern.
        "output": ["refiner"],
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
    "apply_option_a_fastpath_planning",
    "refiner_node",
    "data_query_node",
    "critic_node",
    "historian_node",
    "synthesis_node",
    "final_node",  # ✅ Option A terminal node
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
