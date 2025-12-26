"""
LangGraph state schemas for OSSS agents.

This module provides TypedDict definitions for type-safe state management
in LangGraph StateGraph execution. Each agent output is strictly typed
to ensure consistency and enable proper validation.

Design Principles:
- Type safety through TypedDict definitions
- Clear separation of agent outputs
- Validation helpers for state integrity
- Comprehensive documentation for maintainability
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import operator
from typing import Any, Annotated, Dict, List, Optional, Union

from typing_extensions import TypedDict


def merge_structured_outputs(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two structured output dicts for concurrent LangGraph updates.

    This reducer allows multiple agents (e.g., critic and historian) to
    write to structured_outputs in parallel without conflicts. The right
    dict values override left dict values for matching keys.
    """
    return {**left, **right}


class RefinerState(TypedDict):
    """
    Output schema for the RefinerAgent.

    The RefinerAgent transforms raw user queries into structured,
    clarified prompts for downstream processing.
    """

    refined_question: str
    """The clarified and structured version of the original query."""

    topics: List[str]
    """List of identified topics and themes in the query."""

    confidence: float
    """Confidence score (0.0-1.0) in the refinement quality."""

    processing_notes: Optional[str]
    """Optional notes about the refinement process."""

    timestamp: str
    """ISO timestamp when refinement was completed."""


class DataQueryState(TypedDict, total=False):
    """
    Output schema for the DataQueryAgent.

    This remains for backward compatibility with single data_query usage.
    Option A prefers OSSSState.data_query_results keyed by node-id.
    """

    query: str
    result: Any
    timestamp: str
    agent_output_meta: Dict[str, Any]


class CriticState(TypedDict):
    """
    Output schema for the CriticAgent.

    The CriticAgent provides analytical critique and evaluation
    of the refined query and suggests improvements.
    """

    critique: str
    """Detailed critique of the refined question and approach."""

    suggestions: List[str]
    """List of specific improvement suggestions."""

    severity: str
    """Severity level: 'low', 'medium', 'high', 'critical'."""

    strengths: List[str]
    """Identified strengths in the current approach."""

    weaknesses: List[str]
    """Identified weaknesses or gaps in the approach."""

    confidence: float
    """Confidence score (0.0-1.0) in the critique accuracy."""

    timestamp: str
    """ISO timestamp when critique was completed."""


class HistorianState(TypedDict):
    """
    Output schema for the HistorianAgent.

    The HistorianAgent retrieves and analyzes historical context
    using intelligent search and LLM-powered relevance analysis.
    """

    historical_summary: str
    """Synthesized historical context relevant to the current query."""

    retrieved_notes: List[str]
    """List of filepaths for notes that were retrieved and used."""

    search_results_count: int
    """Number of search results found before filtering."""

    filtered_results_count: int
    """Number of results after relevance filtering."""

    search_strategy: str
    """Type of search strategy used (e.g., 'hybrid', 'tag-based', 'keyword')."""

    topics_found: List[str]
    """List of topics identified in the retrieved historical content."""

    confidence: float
    """Confidence score (0.0-1.0) in the historical context relevance."""

    llm_analysis_used: bool
    """Whether LLM was used for relevance analysis and synthesis."""

    metadata: Dict[str, Any]
    """Additional metadata about the historical search process."""

    timestamp: str
    """ISO timestamp when historical analysis was completed."""


class SynthesisState(TypedDict):
    """
    Output schema for the SynthesisAgent.

    The SynthesisAgent generates final synthesis from multiple
    agent outputs, creating coherent and comprehensive analysis.
    """

    final_analysis: str
    """Comprehensive final analysis integrating all inputs."""

    key_insights: List[str]
    """List of key insights derived from the analysis."""

    sources_used: List[str]
    """List of source agents/outputs used in synthesis."""

    themes_identified: List[str]
    """Major themes identified across all inputs."""

    conflicts_resolved: int
    """Number of conflicts resolved during synthesis."""

    confidence: float
    """Confidence score (0.0-1.0) in the synthesis quality."""

    metadata: Dict[str, Any]
    """Additional metadata about the synthesis process."""

    timestamp: str
    """ISO timestamp when synthesis was completed."""


class ExecutionMetadata(TypedDict):
    """
    Metadata about the LangGraph execution process.
    """

    execution_id: str
    """Unique identifier for this execution."""

    correlation_id: Optional[str]
    """Correlation ID for event tracking and WebSocket filtering."""

    start_time: str
    """ISO timestamp when execution started."""

    orchestrator_type: str
    """Type of orchestrator: 'langgraph-real'."""

    agents_requested: List[str]
    """List of agents requested for execution."""

    execution_mode: str
    """Execution mode: 'langgraph-real'."""

    phase: str
    """Implementation phase: 'phase2_0'."""

class FinalState(TypedDict):
    """
    Output schema for the FinalAgent.

    The FinalAgent produces the user-facing answer,
    optionally using RAG and other agent outputs.
    """

    final_answer: str
    """User-facing final answer text."""

    used_rag: bool
    """Whether RAG context actually influenced this answer."""

    rag_excerpt: Optional[str]
    """Optional excerpt of RAG context surfaced in the answer."""

    sources_used: List[str]
    """List of sources or agents referenced (e.g. ['refiner', 'historian'])."""

    timestamp: str
    """ISO timestamp when the final answer was produced."""


class OSSSState(TypedDict):
    """
    Master state schema for OSSS LangGraph execution.

    This represents the complete state that flows through the
    LangGraph StateGraph during execution. Each agent contributes
    its typed output to this shared state.
    """

    # Core input
    query: str
    """The original user query to process."""

    # Agent outputs (populated during execution)
    refiner: Optional[RefinerState]
    """RefinerState from the RefinerAgent (populated after refiner node)."""

    critic: Optional[CriticState]
    """Output from the CriticAgent (populated after critic node)."""

    historian: Optional[HistorianState]
    """Output from the HistorianAgent (populated after historian node)."""

    synthesis: Optional[SynthesisState]
    """Output from the SynthesisAgent (populated after synthesis node)."""

    # Backward-compatible single data_query slot (legacy)
    data_query: Optional[DataQueryState]
    """Legacy data query output (single). Prefer data_query_results for Option A."""

    # Data query planning/execution (Option A)
    planned_data_query_nodes: List[str]
    """Ordered list of data_query node IDs planned by routing (e.g., ['data_query:teachers'])."""

    completed_data_query_nodes: Annotated[List[str], operator.add]
    """List of data_query node IDs that completed (supports concurrent appends via reducer)."""

    data_query_results: Annotated[Dict[str, Any], merge_structured_outputs]
    """Aggregated per-node results keyed by node ID (supports concurrent merges via reducer)."""

    # Execution tracking
    execution_metadata: ExecutionMetadata
    """Metadata about the current execution."""

    # Error handling
    errors: Annotated[List[Dict[str, Any]], operator.add]
    """List of errors encountered during execution."""

    # Success tracking
    successful_agents: Annotated[List[str], operator.add]
    """List of agents that completed successfully."""

    failed_agents: Annotated[List[str], operator.add]
    """List of agents that failed during execution."""

    # Structured outputs (for API/database persistence)
    structured_outputs: Annotated[Dict[str, Any], merge_structured_outputs]
    """Full Pydantic model outputs from agents for database/API persistence."""

    final: Optional[FinalState]
    """Output from the FinalAgent (user-facing answer)."""

    execution_state: Dict[str, Any]
    rag_context: str
    rag_snippet: str
    rag_hits: List[Any]

# Type aliases for improved clarity
LangGraphState = OSSSState
"""Alias for OSSSState to improve code readability."""

AgentStateUnion = Union[RefinerState, CriticState, HistorianState, SynthesisState]
"""Union type for any agent output schema."""


def create_initial_state(
    query: str,
    execution_id: str,
    correlation_id: Optional[str] = None,
) -> OSSSState:
    now = datetime.now(timezone.utc).isoformat()

    return OSSSState(
        query=query,
        refiner=None,
        critic=None,
        historian=None,
        synthesis=None,
        data_query=None,
        planned_data_query_nodes=[],
        completed_data_query_nodes=[],
        data_query_results={},
        execution_metadata=ExecutionMetadata(
            execution_id=execution_id,
            correlation_id=correlation_id,
            start_time=now,
            orchestrator_type="langgraph-real",
            agents_requested=["refiner", "historian", "final"],
            execution_mode="langgraph-real",
            phase="phase2_1",
        ),
        errors=[],
        successful_agents=[],
        failed_agents=[],
        structured_outputs={},

        # 🔹 New RAG/execution fields
        final=None,
        execution_state={},
        rag_context="",
        rag_snippet="",
        rag_hits=[],
    )



def validate_state_integrity(state: OSSSState) -> bool:
    """
    Validate LangGraph state integrity.

    Note: This validates the core invariant fields and any agent outputs that are present.
    It does not require optional/route-dependent fields (e.g., critic/historian/data_query).
    """
    try:
        if not isinstance(state, dict):
            return False

        if not state.get("query"):
            return False

        if not state.get("execution_metadata"):
            return False

        metadata = state["execution_metadata"]
        if not metadata.get("execution_id"):
            return False

        # Validate agent outputs if present
        if state.get("refiner"):
            refiner: Optional[RefinerState] = state["refiner"]
            if refiner is None or not refiner.get("refined_question") or not refiner.get("timestamp"):
                return False

        if state.get("critic"):
            critic: Optional[CriticState] = state["critic"]
            if critic is None or not critic.get("critique") or not critic.get("timestamp"):
                return False

        if state.get("historian"):
            historian: Optional[HistorianState] = state["historian"]
            if historian is None or not historian.get("historical_summary") or not historian.get("timestamp"):
                return False

        if state.get("synthesis"):
            synthesis: Optional[SynthesisState] = state["synthesis"]
            if synthesis is None or not synthesis.get("final_analysis") or not synthesis.get("timestamp"):
                return False

        if state.get("final"):
            final: Optional[FinalState] = state["final"]
            if (
                    final is None
                    or not final.get("final_answer")
                    or not final.get("timestamp")
            ):
                return False

        return True
    except (KeyError, TypeError):
        return False


def get_agent_state(state: OSSSState, agent_name: str) -> Optional[AgentStateUnion]:
    """
    Get typed agent state from state.
    """
    agent_name = agent_name.lower()

    if agent_name == "refiner":
        return state.get("refiner")
    if agent_name == "critic":
        return state.get("critic")
    if agent_name == "historian":
        return state.get("historian")
    if agent_name == "synthesis":
        return state.get("synthesis")
    return None


def set_agent_state(state: OSSSState, agent_name: str, output: AgentStateUnion) -> OSSSState:
    """
    Set typed agent state in state.

    Note: This function preserves reducer semantics by only appending a single agent_name
    to successful_agents per call.
    """
    new_state = state.copy()

    # Deep copy mutable lists (handle partial state safely)
    new_state["successful_agents"] = (
        state.get("successful_agents", []).copy()
        if isinstance(state.get("successful_agents"), list)
        else []
    )
    new_state["failed_agents"] = (
        state.get("failed_agents", []).copy()
        if isinstance(state.get("failed_agents"), list)
        else []
    )
    new_state["errors"] = state.get("errors", []).copy() if isinstance(state.get("errors"), list) else []

    agent_name = agent_name.lower()

    if agent_name == "refiner" and isinstance(output, dict):
        new_state["refiner"] = output  # type: ignore[assignment]
    elif agent_name == "critic" and isinstance(output, dict):
        new_state["critic"] = output  # type: ignore[assignment]
    elif agent_name == "historian" and isinstance(output, dict):
        new_state["historian"] = output  # type: ignore[assignment]
    elif agent_name == "synthesis" and isinstance(output, dict):
        new_state["synthesis"] = output  # type: ignore[assignment]

    if agent_name not in new_state["successful_agents"]:
        new_state["successful_agents"].append(agent_name)

    return new_state


def record_agent_error(state: OSSSState, agent_name: str, error: Exception) -> OSSSState:
    """
    Record agent execution error in state.

    Handles both complete and partial state objects gracefully.
    """
    new_state = state.copy()

    new_state["successful_agents"] = (
        state.get("successful_agents", []).copy()
        if isinstance(state.get("successful_agents"), list)
        else []
    )
    new_state["failed_agents"] = (
        state.get("failed_agents", []).copy()
        if isinstance(state.get("failed_agents"), list)
        else []
    )
    new_state["errors"] = state.get("errors", []).copy() if isinstance(state.get("errors"), list) else []

    error_record = {
        "agent": agent_name,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    new_state["errors"].append(error_record)

    if agent_name not in new_state["failed_agents"]:
        new_state["failed_agents"].append(agent_name)

    return new_state


@dataclass
class OSSSContext:
    """
    Context schema for OSSS LangGraph execution.

    This context is passed to all nodes during graph execution,
    providing thread-scoped information and configuration.
    """

    thread_id: str
    execution_id: str
    query: str
    correlation_id: Optional[str] = None
    enable_checkpoints: bool = False


__all__ = [
    "OSSSState",
    "LangGraphState",
    "RefinerState",
    "DataQueryState",
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
