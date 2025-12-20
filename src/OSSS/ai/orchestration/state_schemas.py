"""
LangGraph state schemas for OSSS agents (refactored).

Refactor goals (aligned with recent node_wrappers + GraphFactory changes):
- Keep OSSSState as a TypedDict with reducer annotations (LangGraph concurrency-safe).
- Make the "guard pipeline" keys match the new graph builder + node wrappers:
    - data_views (plural) not data_view
    - guard_decision stored at top-level for routing
    - execution_state remains the "legacy bag" for node wrappers to stash inputs/outputs
- Add query_profile + routing_decision fields (node_wrappers Option B uses them).
- Make OSSSContext resilient to runtime kwargs (emit_events) to avoid crashes.
- Make create_initial_state NOT hardcode requested agents (GraphFactory/orchestrator decide).
- Keep helpers minimal + tolerant of partial state (nodes often return patches).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import operator
from typing import Any, Dict, List, Optional, Union, Annotated

from typing_extensions import TypedDict


# -----------------------------------------------------------------------------
# Reducers (for concurrent updates)
# -----------------------------------------------------------------------------
def merge_structured_outputs(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two dicts for concurrent LangGraph updates.
    Right wins for overlapping keys.
    """
    if not isinstance(left, dict):
        left = {}
    if not isinstance(right, dict):
        right = {}
    return {**left, **right}


# -----------------------------------------------------------------------------
# Guard pipeline payloads (normalized)
# -----------------------------------------------------------------------------
class GuardState(TypedDict, total=False):
    allowed: bool
    decision: str  # "allow" | "block" | "requires_confirmation"
    action: str
    reason: str
    message: str
    safe_response: str
    timestamp: str


class AnswerSearchState(TypedDict, total=False):
    ok: bool
    type: str  # "answer_search"
    answer_text: str
    sources: List[Any]
    fallback: bool
    reason: str
    timestamp: str


class UIResponseState(TypedDict, total=False):
    status: str  # "ok" | "blocked" | "requires_confirmation"
    message: str
    sources: List[Any]
    timestamp: str
    mode: str  # optional: "answer_search" | "data_views"


# -----------------------------------------------------------------------------
# Agent outputs (kept compatible with node_wrappers)
# -----------------------------------------------------------------------------
class RefinerState(TypedDict, total=False):
    refined_question: str
    topics: List[str]
    confidence: float
    processing_notes: Optional[str]
    timestamp: str
    agent_output_meta: Dict[str, Any]


class CriticState(TypedDict, total=False):
    critique: str
    suggestions: List[str]
    severity: str
    strengths: List[str]
    weaknesses: List[str]
    confidence: float
    timestamp: str
    agent_output_meta: Dict[str, Any]


class HistorianState(TypedDict, total=False):
    historical_summary: str
    retrieved_notes: List[str]
    search_results_count: int
    filtered_results_count: int
    search_strategy: str
    topics_found: List[str]
    confidence: float
    llm_analysis_used: bool
    metadata: Dict[str, Any]
    timestamp: str
    agent_output_meta: Dict[str, Any]


class SynthesisState(TypedDict, total=False):
    final_analysis: str
    key_insights: List[str]
    sources_used: List[str]
    themes_identified: List[str]
    conflicts_resolved: int
    confidence: float
    metadata: Dict[str, Any]
    timestamp: str
    agent_output_meta: Dict[str, Any]


# -----------------------------------------------------------------------------
# Execution metadata (make optional-ish + tolerant)
# -----------------------------------------------------------------------------
class ExecutionMetadata(TypedDict, total=False):
    execution_id: str
    correlation_id: Optional[str]
    start_time: str
    orchestrator_type: str
    agents_requested: List[str]
    execution_mode: str
    phase: str


# -----------------------------------------------------------------------------
# OSSSState (master LangGraph state)
# -----------------------------------------------------------------------------
class OSSSState(TypedDict, total=False):
    # Core input
    query: str

    # Optional: profiling info injected by orchestrator (use_llm_intent)
    query_profile: Dict[str, Any]
    routing_decision: Dict[str, Any]

    # Agent outputs
    refiner: Optional[RefinerState]
    critic: Optional[CriticState]
    historian: Optional[HistorianState]
    synthesis: Optional[SynthesisState]

    # Guard pipeline routing + outputs
    guard_decision: Optional[str]
    guard: Optional[GuardState]
    answer_search: Optional[AnswerSearchState]

    # Data views output (plural, matches node_wrappers + GraphFactory)
    data_views: Optional[Dict[str, Any]]

    # Final UI response
    final_response: Optional[UIResponseState]
    ui_response: Optional[UIResponseState]  # legacy convenience

    # Execution tracking
    execution_metadata: ExecutionMetadata

    # Legacy / wrapper execution bag (node_wrappers uses this heavily)
    execution_state: Dict[str, Any]

    # Error + success tracking (reducers support parallel node updates)
    errors: Annotated[List[Dict[str, Any]], operator.add]
    successful_agents: Annotated[List[str], operator.add]
    failed_agents: Annotated[List[str], operator.add]

    # Structured outputs (reducers support parallel node updates)
    structured_outputs: Annotated[Dict[str, Any], merge_structured_outputs]


# Type aliases
LangGraphState = OSSSState
AgentStateUnion = Union[RefinerState, CriticState, HistorianState, SynthesisState]


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_initial_state(query: str, execution_id: str, correlation_id: Optional[str] = None) -> OSSSState:
    """
    Create the initial LangGraph state.

    Note:
    - Do NOT hardcode agents_requested here. Orchestrator/GraphFactory decide the plan.
    - Keep this tolerant: many nodes return partial patches, and reducers merge.
    """
    now = _now_iso()
    return OSSSState(
        query=query,
        refiner=None,
        critic=None,
        historian=None,
        synthesis=None,
        guard_decision=None,
        guard=None,
        answer_search=None,
        data_views=None,
        final_response=None,
        ui_response=None,
        query_profile={},
        routing_decision={},
        execution_state={},
        execution_metadata=ExecutionMetadata(
            execution_id=execution_id,
            correlation_id=correlation_id,
            start_time=now,
            orchestrator_type="langgraph-real",
            execution_mode="langgraph-real",
            phase="phase2_1",
        ),
        errors=[],
        successful_agents=[],
        failed_agents=[],
        structured_outputs={},
    )


def validate_state_integrity(state: OSSSState) -> bool:
    """
    Lightweight integrity check.

    Keep permissive: in LangGraph, node returns are often partial patches.
    This should validate "minimum viable state" rather than strict completeness.
    """
    if not isinstance(state, dict):
        return False

    q = state.get("query")
    if not isinstance(q, str) or not q:
        return False

    meta = state.get("execution_metadata")
    if meta is not None and not isinstance(meta, dict):
        return False

    # If execution_metadata present, execution_id should exist
    if isinstance(meta, dict):
        eid = meta.get("execution_id")
        if eid is not None and (not isinstance(eid, str) or not eid):
            return False

    return True


def get_agent_state(state: OSSSState, agent_name: str) -> Optional[AgentStateUnion]:
    name = (agent_name or "").strip().lower()
    if name in {"refiner", "critic", "historian", "synthesis"}:
        return state.get(name)  # type: ignore[return-value]
    return None


def set_agent_state(state: OSSSState, agent_name: str, output: AgentStateUnion) -> OSSSState:
    """
    Set an agent output into the state, returning a shallow copy.

    Prefer using node returns + reducers in LangGraph; this helper is mainly for tests/utilities.
    """
    name = (agent_name or "").strip().lower()
    new_state: OSSSState = dict(state)  # shallow copy is enough for TypedDict
    if name in {"refiner", "critic", "historian", "synthesis"} and isinstance(output, dict):
        new_state[name] = output  # type: ignore[literal-required]

    # Track success (non-reducer-safe outside graph, but fine for utilities)
    sa = list(state.get("successful_agents") or [])
    if name and name not in sa:
        sa.append(name)
    new_state["successful_agents"] = sa  # type: ignore[assignment]
    return new_state


def record_agent_error(state: OSSSState, agent_name: str, error: Exception) -> OSSSState:
    """
    Record an agent error into state in a tolerant way.
    Safe for partial state objects.
    """
    name = (agent_name or "").strip().lower()
    new_state: OSSSState = dict(state)

    errors = list(state.get("errors") or [])
    failed = list(state.get("failed_agents") or [])

    errors.append(
        {
            "agent": name or agent_name,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": _now_iso(),
        }
    )
    if name and name not in failed:
        failed.append(name)

    new_state["errors"] = errors  # type: ignore[assignment]
    new_state["failed_agents"] = failed  # type: ignore[assignment]
    return new_state


# -----------------------------------------------------------------------------
# OSSSContext (runtime context passed to nodes)
# -----------------------------------------------------------------------------
@dataclass
class OSSSContext:
    """
    Context passed to LangGraph nodes.

    IMPORTANT:
    - LangGraph runtime may pass additional kwargs (e.g. emit_events).
      Accept it to avoid: OSSSContext.__init__() got unexpected keyword argument 'emit_events'
    - Also accept arbitrary extras for forward compatibility (ignored).
    """
    thread_id: str
    execution_id: str
    query: str
    correlation_id: Optional[str] = None
    enable_checkpoints: bool = False

    # LangGraph/runtime flags
    emit_events: bool = False

    # Forward compatibility: ignore unexpected kwargs without crashing.
    def __init__(
        self,
        thread_id: str,
        execution_id: str,
        query: str,
        correlation_id: Optional[str] = None,
        enable_checkpoints: bool = False,
        emit_events: bool = False,
        **_: Any,
    ) -> None:
        self.thread_id = thread_id
        self.execution_id = execution_id
        self.query = query
        self.correlation_id = correlation_id
        self.enable_checkpoints = enable_checkpoints
        self.emit_events = emit_events


__all__ = [
    "OSSSState",
    "LangGraphState",
    "GuardState",
    "AnswerSearchState",
    "UIResponseState",
    "RefinerState",
    "CriticState",
    "HistorianState",
    "SynthesisState",
    "AgentStateUnion",
    "ExecutionMetadata",
    "OSSSContext",
    "create_initial_state",
    "validate_state_integrity",
    "get_agent_state",
    "set_agent_state",
    "record_agent_error",
    "merge_structured_outputs",
]
