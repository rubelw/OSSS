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


from OSSS.ai.orchestration.routing.historian import should_run_historian
from OSSS.ai.orchestration.routing.db_query_router import DBQueryRouter


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

    # IMPORTANT: do not clobber a richer execution_config already present
    existing_ec = exec_state.get("execution_config")
    if isinstance(existing_ec, dict) and existing_ec:
        merged_ec = dict(existing_ec)
        merged_ec.update(ec)  # state/runtime view wins for overlapping keys
        exec_state["execution_config"] = merged_ec
        ec = merged_ec
    else:
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
        or exec_state.get("rag_context")      # already present
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
        or getattr(runtime.context, "query", None)
        or ""
    ).strip()

    if not user_question:
        # Nothing sensible to embed
        exec_state["rag_enabled"] = False
        return

    # Allow top_k to come from either rag_cfg.top_k or root ec.top_k
    index = rag_cfg.get("index", "main")
    top_k = int(rag_cfg.get("top_k") or ec.get("top_k") or 5)
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

    # ✅ Normalize canonical bookkeeping containers (so API + telemetry never see empty/missing)
    exec_state.setdefault("successful_agents", [])
    exec_state.setdefault("failed_agents", [])
    exec_state.setdefault("errors", [])
    exec_state.setdefault("structured_outputs", {})
    exec_state.setdefault("agent_output_index", {})
    exec_state.setdefault("agent_outputs", {})
    exec_state.setdefault("agent_output_meta", {})
    exec_state.setdefault("effective_queries", {})  # used by _record_effective_query
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


def _merge_successful_agents(state: OSSSState, *agents: str) -> List[str]:
    """
    Merge one or more agent names into state.successful_agents.

    IMPORTANT:
      - Always returns a **list** (never a set)
      - Ensures uniqueness while preserving original order as much as possible
      - Keeps state["successful_agents"] as a list so LangGraph's list
        aggregator can safely concatenate without type errors.
    """
    existing = state.get("successful_agents")
    merged: List[str] = []

    # Normalize existing to a list, preserving order where we can
    if isinstance(existing, list):
        for a in existing:
            if isinstance(a, str) and a and a not in merged:
                merged.append(a)
    elif isinstance(existing, (set, tuple)):
        for a in existing:
            if isinstance(a, str) and a and a not in merged:
                merged.append(a)

    # Add new agents, keeping uniqueness
    for a in agents:
        if isinstance(a, str) and a and a not in merged:
            merged.append(a)

    # Persist back as list so future reads are consistent
    state["successful_agents"] = merged
    return merged


def _normalize_target_name(target: str) -> str:
    """
    Normalize route/router targets to match graph node ids.

    Handles 'END'/'end' for safety as discussed.
    """
    t = (target or "").strip()
    if not t:
        return ""
    if t.upper() == "END":
        return "end"
    return t


def _compute_route_for_planning(exec_state: Dict[str, Any], query: str) -> str:
    """
    Option A helper: compute pre-compilation routing using DBQueryRouter signals.
    Persists canonical keys into exec_state and returns chosen_target.
    """
    q = (query or "").strip()
    request = {"query": q}

    router = DBQueryRouter()
    signals = router.compute(exec_state, request)

    target = (signals.target or "").strip().lower()

    if target == "data_query":
        exec_state["route"] = "data_query"
        exec_state.setdefault("route_key", signals.key or "action")
    else:
        exec_state["route"] = exec_state.get("route") or "refiner"
        exec_state.setdefault("route_key", "informational")

    # Persist observability fields (router is pure, so we set these here)
    exec_state["route_locked"] = bool(signals.locked)
    if signals.reason:
        exec_state["route_reason"] = signals.reason

    # Optional: keep the whole signals bundle around for logging/debug
    exec_state["routing_signals"] = {
        "target": signals.target,
        "locked": signals.locked,
        "reason": signals.reason,
        "key": signals.key,
    }

    return exec_state["route"]



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

    Behavior (clamped to the two supported patterns):

      - If caller did NOT explicitly set a graph_pattern, then:
          • For DB/action routes (chosen_target == "data_query"):
                graph_pattern = "data_query"
                planned_agents = ["refiner", "data_query"]

          • For informational/answer routes (anything else):
                graph_pattern = "standard"
                planned_agents = ["refiner", "final"]

    NOTE:
      - This is intentionally *not* invoked from route_gate_node.
      - Orchestrator may further normalize agents, but pattern names are
        always one of {"standard", "data_query"}.

    IMPORTANT FIX:
      - If chosen_target is empty/None, we will try to compute it from the
        execution_state + query (if present) via DBQueryRouter, and persist
        route fields into execution_state so planners don't miss it.
    """
    ec = _ensure_execution_config(exec_state)

    # Respect existing caller override if provided
    existing = ec.get("graph_pattern")
    if isinstance(existing, str) and existing.strip():
        return

    # If caller didn't pass a target, attempt to compute one (planner may call
    # us before it computed route, or may have lost it).
    ct = _normalize_target_name(chosen_target)
    if not ct:
        q = (
            exec_state.get("query")
            or exec_state.get("user_question")
            or exec_state.get("original_query")
            or exec_state.get("raw_user_text")
            or ""
        )
        try:
            ct = _compute_route_for_planning(exec_state, str(q))
        except Exception as e:
            logger.warning(f"[planning] failed to compute route via DBQueryRouter: {e}")
            ct = ""

    # Clamp to supported patterns
    if ct == "data_query":
        ec["graph_pattern"] = "data_query"
        exec_state["planned_agents"] = ["refiner", "data_query"]
        exec_state.setdefault("route", "data_query")
        exec_state.setdefault("route_key", "action")
    else:
        ec["graph_pattern"] = "standard"
        exec_state["planned_agents"] = ["refiner", "final"]
        exec_state.setdefault("route", ct or "refiner")
        exec_state.setdefault("route_key", "informational")


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

    Pattern 1: single state universe
      - OSSSState["execution_state"] is canonical
      - AgentContext.execution_state is a direct reference to that dict
    """
    _ = AgentContextStateBridge()  # retained for future compatibility / tooling

    if "query" not in state:
        raise ValueError("State must contain a query field")

    # ---- Core query wiring -------------------------------------------------
    query = state.get("query", "") or ""
    original_query = (state.get("original_query") or "").strip() or query

    # Canonical execution_state dict (ONE universe)
    exec_state = _ensure_exec_state(state)  # ensures state["execution_state"] is a dict

    # Build context and attach the SAME dict as execution_state
    context = AgentContext(query=query)
    context.execution_state = exec_state  # <-- critical: shared reference

    # ---- RAG + routing / metadata hydration into the canonical exec_state --
    # Allow RAG to come from top-level state if orchestrator injected it there.
    for k in ("rag_context", "rag_snippet", "rag_hits", "rag_meta"):
        if k not in exec_state and k in state:
            v = state.get(k)
            if v is not None:
                exec_state[k] = v

    # Make sure FinalAgent and others have a stable view of the question
    exec_state.setdefault("original_query", original_query)
    exec_state.setdefault("user_question", original_query)

    # Surface structured_outputs from top-level state into execution_state
    so = state.get("structured_outputs")
    if isinstance(so, dict):
        existing_so = exec_state.get("structured_outputs")
        if isinstance(existing_so, dict):
            merged = dict(existing_so)
            merged.update(so)
            exec_state["structured_outputs"] = merged
        else:
            exec_state["structured_outputs"] = dict(so)

    # ---- Hydrate prior agent outputs into AgentContext + exec_state --------
    # Refiner
    if state.get("refiner"):
        refiner_state: Optional[RefinerState] = state["refiner"]
        if isinstance(refiner_state, dict):
            refined_question = refiner_state.get("refined_question", "")
            if refined_question:
                context.add_agent_output("refiner", refined_question)
                exec_state["refiner_topics"] = refiner_state.get("topics", [])
                exec_state["refiner_confidence"] = refiner_state.get("confidence", 0.8)

                refiner_full = exec_state.get("refiner_full_text")
                snippet = refiner_full if isinstance(refiner_full, str) and refiner_full.strip() else refined_question
                if snippet.strip():
                    exec_state.setdefault("refiner_snippet", snippet)

    # Derive rag_snippet from rag_context when available
    rag_ctx = exec_state.get("rag_context")
    if rag_ctx is not None and not exec_state.get("rag_snippet"):
        rag_snippet = _to_text(rag_ctx)
        if rag_snippet.strip():
            exec_state["rag_snippet"] = rag_snippet

    # Data query (Option A: prefer data_query_results)
    latest_payload = _pick_latest_data_query_payload(state)
    if latest_payload is not None:
        dq_text = _to_text(latest_payload)
        if dq_text.strip():
            context.add_agent_output("data_query", dq_text)
        exec_state["data_query_result"] = latest_payload
        latest_node_id = _pick_latest_data_query_node_id(state)
        if latest_node_id:
            exec_state["data_query_node_id"] = latest_node_id
    else:
        # Legacy fallback: state["data_query"].result
        dq_state = state.get("data_query")
        if isinstance(dq_state, dict):
            result = dq_state.get("result")
            if result is not None:
                dq_text = _to_text(result)
                if dq_text.strip():
                    context.add_agent_output("data_query", dq_text)
                exec_state["data_query_result"] = result

    # Critic
    if state.get("critic"):
        critic_state: Optional[CriticState] = state["critic"]
        if isinstance(critic_state, dict):
            critique = critic_state.get("critique", "")
            if critique:
                context.add_agent_output("critic", critique)
                exec_state["critic_suggestions"] = critic_state.get("suggestions", [])
                exec_state["critic_severity"] = critic_state.get("severity", "medium")

    # Historian
    if state.get("historian"):
        historian_state: Optional[HistorianState] = state["historian"]
        if isinstance(historian_state, dict):
            historical_summary = historian_state.get("historical_summary", "")
            if historical_summary:
                context.add_agent_output("historian", historical_summary)
                exec_state["historian_retrieved_notes"] = historian_state.get("retrieved_notes", [])
                exec_state["historian_search_strategy"] = historian_state.get("search_strategy", "hybrid")
                exec_state["historian_topics_found"] = historian_state.get("topics_found", [])
                exec_state["historian_confidence"] = historian_state.get("confidence", 0.8)

    # ---- Execution metadata into exec_state + AgentContext -----------------
    execution_metadata = state.get("execution_metadata", {})
    if isinstance(execution_metadata, dict) and execution_metadata:
        succ = state.get("successful_agents")
        fail = state.get("failed_agents")

        succ_list = list(succ) if isinstance(succ, (list, set, tuple)) else []
        fail_list = list(fail) if isinstance(fail, (list, set, tuple)) else []

        exec_state.update(
            {
                "execution_id": execution_metadata.get("execution_id", ""),
                "orchestrator_type": "langgraph-real",
                "successful_agents": succ_list,
                "failed_agents": fail_list,
            }
        )

    # Also hydrate AgentContext-level tracking for orchestration_api convenience
    succ = state.get("successful_agents")
    fail = state.get("failed_agents")

    if isinstance(succ, (list, set, tuple)):
        context.successful_agents = list(succ)
    if isinstance(fail, (list, set, tuple)):
        context.failed_agents = list(fail)

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

    exec_state = _ensure_exec_state(state)

    router = DBQueryRouter()
    signals = router.compute(exec_state, {"query": original_query or state.get("query", "") or ""})

    chosen_target = _normalize_target_name(signals.target or "refiner")
    route_key = (signals.key or ("action" if chosen_target == "data_query" else "informational"))

    exec_state = _ensure_exec_state(state)

    # Read config for logging only (do NOT mutate planning here; Option A)
    ec_view = _get_execution_config(state, runtime)

    logger.info(
        "Route chosen (view only)",
        extra={
            "graph_pattern": (ec_view.get("graph_pattern") if isinstance(ec_view, dict) else None),
            "planned_agents": exec_state.get("planned_agents"),
        },
    )

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
    exec_state["route_locked"] = bool(signals.locked)
    if signals.reason:
        exec_state["route_reason"] = signals.reason

    exec_state["routing_signals"] = {
        "target": signals.target,
        "locked": signals.locked,
        "reason": signals.reason,
        "key": signals.key,
    }

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

        # ✅ ONE universe: always use the graph's exec_state as canonical
        exec_state = _ensure_exec_state(state)
        if isinstance(context.execution_state, dict):
            exec_state.update(context.execution_state)

        # 1) user_question: prefer promoted query, then runtime.context.query
        if not exec_state.get("user_question"):
            uq = (
                (state.get("query") or "")
                or (state.get("original_query") or "")
                or (runtime.context.query or "")
                or context.query
            )
            if uq:
                exec_state["user_question"] = uq

        # Also keep a stable "question" field (many API layers use this)
        state.setdefault("question", exec_state.get("user_question") or "")

        # 2) refiner_snippet: try refined_question from refiner_state or full markdown
        if not exec_state.get("refiner_snippet"):
            refined_question = ""
            refiner_state = state.get("refiner")
            if isinstance(refiner_state, dict):
                refined_question = (refiner_state.get("refined_question") or "").strip()

            refiner_full = (exec_state.get("refiner_full_text") or "").strip()
            snippet_source = refiner_full or refined_question

            if snippet_source:
                exec_state["refiner_snippet"] = snippet_source

        # 3) 🔥 RAG SNIPPET: bridge orchestrator's rag_context -> what FinalAgent expects
        await _ensure_rag_for_final(state=state, runtime=runtime, exec_state=exec_state)

        if not exec_state.get("rag_snippet"):
            rag_ctx = exec_state.get("rag_context") or state.get("rag_context")
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

        # ✅ Merge agent-side execution_state back into canonical exec_state
        if isinstance(getattr(result_context, "execution_state", None), dict):
            exec_state.update(result_context.execution_state)

        final_text = (result_context.agent_outputs.get("final") or "").strip()
        if not final_text:
            raise NodeExecutionError("Final agent ran but produced no 'final' output")

        rag_snippet = exec_state.get("rag_snippet") or state.get("rag_snippet") or ""
        rag_snippet = (rag_snippet or "").strip()

        sources_used = ["refiner"]
        if state.get("historian"):
            sources_used.append("historian")
        if exec_state.get("data_query_result") or state.get("data_query"):
            sources_used.append("data_query")

        state["final"] = FinalState(
            final_answer=final_text,
            used_rag=bool(rag_snippet),
            rag_excerpt=rag_snippet[:500] or None,
            sources_used=sources_used,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        state["final_output"] = final_text

        # ✅ Canonical structured outputs live in exec_state; mirror to top-level for API.
        structured = exec_state.get("structured_outputs")
        if not isinstance(structured, dict):
            structured = {}
            exec_state["structured_outputs"] = structured

        structured.setdefault("final", final_text)
        state["structured_outputs"] = structured

        # ✅ Record agent outputs in a stable place (telemetry + API debug)
        ao = exec_state.setdefault("agent_outputs", {})
        if isinstance(ao, dict):
            ao["final"] = final_text
        aoi = exec_state.setdefault("agent_output_index", {})
        if isinstance(aoi, dict):
            aoi["final"] = "final"

        succ = _merge_successful_agents(state, "final")
        exec_state["successful_agents"] = list(succ)

        return {
            "execution_state": exec_state,
            "structured_outputs": structured,
            "successful_agents": succ,
            "final": state.get("final"),
            "final_output": final_text,
            "question": state.get("question", "") or exec_state.get("user_question", ""),
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

        # ✅ Merge agent-side execution_state back into canonical exec_state
        exec_state = _ensure_exec_state(state)
        if isinstance(getattr(result_context, "execution_state", None), dict):
            exec_state.update(result_context.execution_state)

        # Full raw text from the LLM
        refiner_raw_output = (result_context.agent_outputs.get("refiner") or "").strip()

        # Canonicalized refined question
        refined_question = canonicalize_dcg(extract_refined_question(refiner_raw_output))

        # ✅ Preserve full refiner text once for downstream consumers (FinalAgent, API, markdown)
        if isinstance(refiner_raw_output, str) and refiner_raw_output.strip():
            exec_state.setdefault("refiner_full_text", refiner_raw_output)

        # ✅ Guardrail: if canonicalization produced junk, fall back to raw
        if isinstance(refined_question, str):
            rq_stripped = refined_question.strip()
            if (
                not rq_stripped
                or not any(ch.isalnum() for ch in rq_stripped)
                or (len(rq_stripped) < 8 and len(refiner_raw_output) > len(rq_stripped) * 2)
            ):
                refined_question = refiner_raw_output

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

        # ✅ Canonical structured outputs live in exec_state; merge + mirror
        structured_outputs = exec_state.get("structured_outputs")
        if not isinstance(structured_outputs, dict):
            structured_outputs = {}
            exec_state["structured_outputs"] = structured_outputs
        if isinstance(getattr(result_context, "execution_state", None), dict):
            so2 = result_context.execution_state.get("structured_outputs")
            if isinstance(so2, dict):
                structured_outputs.update(so2)
        state["structured_outputs"] = structured_outputs

        # ✅ Record agent outputs in a stable place (telemetry + API debug)
        ao = exec_state.setdefault("agent_outputs", {})
        if isinstance(ao, dict):
            ao["refiner"] = refiner_raw_output
        aoi = exec_state.setdefault("agent_output_index", {})
        if isinstance(aoi, dict):
            aoi["refiner"] = "refiner"

        succ = _merge_successful_agents(state, "refiner")
        exec_state["successful_agents"] = list(succ)

        state.setdefault("question", original_for_state or "")

        return {
            "execution_state": exec_state,
            "original_query": original_for_state,
            "query": promoted_query,
            "refiner": refiner_state,
            "successful_agents": succ,
            "structured_outputs": structured_outputs,
            "question": state.get("question", "") or original_for_state,
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

        canonical_value = payload if payload is not None else None

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

        succ_agents = ["data_query"]
        if dq_node_id != "data_query":
            succ_agents.append(dq_node_id)
        succ = _merge_successful_agents(state, *succ_agents)
        exec_state["successful_agents"] = list(succ)

        exec_state["data_query_result"] = canonical_value
        exec_state["data_query_node_id"] = dq_node_id

        # Option A: append/merge instead of overwrite
        completed_nodes = list(state.get("completed_data_query_nodes") or [])
        if dq_node_id not in completed_nodes:
            completed_nodes.append(dq_node_id)

        dq_results = dict(state.get("data_query_results") or {})
        dq_results[dq_node_id] = canonical_value

        planned_nodes = list(state.get("planned_data_query_nodes") or [])
        if not planned_nodes:
            planned_nodes = [dq_node_id]

        option_a_updates: Dict[str, Any] = {
            "completed_data_query_nodes": completed_nodes,
            "data_query_results": dq_results,
            "planned_data_query_nodes": planned_nodes,
            "successful_agents": succ,
        }

        return {
            "execution_state": exec_state,
            "data_query": data_query_state,  # legacy compatibility
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

        succ = _merge_successful_agents(state, "critic")
        exec_state["successful_agents"] = list(succ)

        return {
            "execution_state": exec_state,
            "critic": critic_state,
            "successful_agents": succ,
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

        succ = _merge_successful_agents(state)
        exec_state["successful_agents"] = list(succ)

        return {
            "execution_state": exec_state,
            "historian": None,
            "successful_agents": succ,
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

        succ = _merge_successful_agents(state, "historian")
        exec_state["successful_agents"] = list(succ)

        return {
            "execution_state": exec_state,
            "historian": historian_state,
            "successful_agents": succ,
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
    (Kept for compatibility; in the two-pattern world, synthesis may not be used
    by the default "standard" or "data_query" patterns, but it remains callable
    for any custom graphs that still include it.)
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

        succ = _merge_successful_agents(state, "synthesis")
        exec_state["successful_agents"] = list(succ)

        return {
            "execution_state": exec_state,
            "synthesis": synthesis_state,
            "successful_agents": succ,
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
        # output is a terminal node in older/custom patterns; it depends on refiner as well.
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
    "final_node",  # ✅ terminal node in "standard" pattern
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
