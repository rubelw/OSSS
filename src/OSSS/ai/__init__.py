# src/OSSS/ai/langchain/__init__.py
from __future__ import annotations

from typing import Any, Dict, TypedDict
import logging

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from OSSS.ai.langchain.agents.student_info.student_info_table_agent import StudentInfoTableAgent
from OSSS.ai.langchain.registry import (
    register_langchain_agent,
    run_agent as registry_run_agent,
)

logger = logging.getLogger("OSSS.ai.langchain")

# ---------------------------------------------------------------------------
# Intent → LangChain agent name mapping
# ---------------------------------------------------------------------------

INTENT_TO_LC_AGENT: dict[str, str] = {
    # bridge from old behavior: generic "langchain_agent" goes to student_info_table
    "langchain_agent": "lc.student_info_table",
    "student_info": "lc.student_info_table",
    # "students_missing_assignments": "lc.students_missing_assignments",
    # add more as you build them...
}

DEFAULT_AGENT_NAME = "lc.student_info_table"

# ---------------------------------------------------------------------------
# Register concrete agents with the registry
# ---------------------------------------------------------------------------

# Student info table agent (uses the StructuredTool internally)
register_langchain_agent(StudentInfoTableAgent())

# add more agents here as you implement them:
# from OSSS.ai.langchain.agents.students_missing_assignments_agent import (
#     StudentsMissingAssignmentsAgent,
# )
# register_langchain_agent(StudentsMissingAssignmentsAgent())


# ---------------------------------------------------------------------------
# LangGraph state + nodes
# ---------------------------------------------------------------------------


class LangchainState(TypedDict, total=False):
    """
    State carried through the LangGraph workflow.

    Fields:
      - raw_message: original message from the caller
      - normalized_message: cleaned/normalized text used by the agent
      - session_id: logical chat session id
      - intent: optional semantic intent label
      - agent_name: resolved LangChain agent name (e.g. "lc.student_info_table")
      - result: final result dict returned from the LangChain registry agent
    """

    raw_message: str
    normalized_message: str
    session_id: str
    intent: str | None
    agent_name: str | None
    result: Dict[str, Any]


async def _node_preprocess(state: LangchainState) -> LangchainState:
    """
    Normalize the incoming message.

    For now this just strips whitespace and collapses spaces, but this is the
    right place to:
      - rewrite "show me" → "Generate a table of"
      - detect simple commands
      - add extra metadata, etc.
    """
    raw = state["raw_message"]
    # simple normalization for now
    normalized = " ".join(raw.strip().split())

    logger.debug(
        "LangGraph[langchain]._node_preprocess: session_id=%s raw=%r normalized=%r",
        state["session_id"],
        raw,
        normalized,
    )

    return {"normalized_message": normalized}


async def _node_select_agent(state: LangchainState) -> LangchainState:
    """
    Decide which LangChain agent to call.

    Priority:
      1) If agent_name is already provided -> keep it.
      2) Else if intent is provided and in INTENT_TO_LC_AGENT -> map it.
      3) Else fall back to DEFAULT_AGENT_NAME.
    """
    agent_name = state.get("agent_name")
    intent = state.get("intent")

    if agent_name:
        resolved = agent_name
        reason = "explicit agent_name from caller"
    elif intent and intent in INTENT_TO_LC_AGENT:
        resolved = INTENT_TO_LC_AGENT[intent]
        reason = f"mapped from intent={intent!r}"
    else:
        resolved = DEFAULT_AGENT_NAME
        reason = "fallback to DEFAULT_AGENT_NAME"

    logger.info(
        "LangGraph[langchain]._node_select_agent: session_id=%s intent=%r -> agent=%s (%s)",
        state["session_id"],
        intent,
        resolved,
        reason,
    )

    return {"agent_name": resolved}


async def _node_run_registry_agent(state: LangchainState) -> LangchainState:
    """
    Call the existing registry_run_agent with the normalized message.
    """
    normalized = state.get("normalized_message") or state["raw_message"]
    session_id = state["session_id"]
    agent_name = state["agent_name"] or DEFAULT_AGENT_NAME

    logger.info(
        "LangGraph[langchain]._node_run_registry_agent: session_id=%s agent_name=%s message=%r",
        session_id,
        agent_name,
        normalized,
    )

    result = await registry_run_agent(
        message=normalized,
        session_id=session_id,
        agent_name=agent_name,
    )

    return {"result": result}


async def _node_postprocess(state: LangchainState) -> LangchainState:
    """
    Optional post-processing / formatting layer.

    This is where you could:
      - Wrap table outputs in markdown or HTML
      - Normalize field names
      - Add human-readable headers, etc.

    For now it's a pass-through, but we keep it as a distinct node so you can
    easily extend it later.
    """
    result = state["result"]

    # Example: ensure "reply" is always a string (if your agents use that convention)
    reply = result.get("reply")
    if isinstance(reply, list):
        # Just an example heuristic: join list replies into a single string.
        result["reply"] = "\n".join(str(x) for x in reply)

    logger.debug(
        "LangGraph[langchain]._node_postprocess: session_id=%s keys=%s",
        state["session_id"],
        list(result.keys()),
    )

    return {"result": result}


# ---------------------------------------------------------------------------
# Compile LangGraph workflow with SQLite checkpointer
# ---------------------------------------------------------------------------

# Use the dedicated volume-mounted path for persistence:
#   langgraph_data:/workspace/langgraph_data
_langgraph_db_path = "/workspace/langgraph_data/osss_langgraph.db"
_langchain_checkpointer = SqliteSaver.from_conn_string(_langgraph_db_path)

_langchain_builder = StateGraph(LangchainState)
_langchain_builder.add_node("preprocess", _node_preprocess)
_langchain_builder.add_node("select_agent", _node_select_agent)
_langchain_builder.add_node("run_registry_agent", _node_run_registry_agent)
_langchain_builder.add_node("postprocess", _node_postprocess)

_langchain_builder.add_edge(START, "preprocess")
_langchain_builder.add_edge("preprocess", "select_agent")
_langchain_builder.add_edge("select_agent", "run_registry_agent")
_langchain_builder.add_edge("run_registry_agent", "postprocess")
_langchain_builder.add_edge("postprocess", END)

_langchain_graph = _langchain_builder.compile(checkpointer=_langchain_checkpointer)


# ---------------------------------------------------------------------------
# Public entry point used by RouterAgent and /ai/langchain/chat
# ---------------------------------------------------------------------------

async def run_agent(
    message: str,
    session_id: str,
    agent_name: str | None = None,
    intent: str | None = None,
) -> Dict[str, Any]:
    """
    Single entry-point used by RouterAgent and /ai/langchain/chat.

    - RouterAgent can pass `agent_name` and optionally `intent` (for logging).
    - The FastAPI /ai/langchain/chat endpoint can just pass message + session_id.
    - Under the hood we:
        1) Build LangGraph state (raw_message, session_id, agent_name, intent).
        2) Invoke the LangGraph workflow with a SQLite checkpointer.
        3) Return the `result` field produced by the last node.
    """
    logger.info(
        "LangChain.run_agent (via LangGraph) called: session_id=%s agent_name=%s intent=%s message=%r",
        session_id,
        agent_name,
        intent,
        message,
    )

    initial_state: LangchainState = {
        "raw_message": message,
        "session_id": session_id,
        "agent_name": agent_name,
        "intent": intent,
    }

    # Use just session_id as the thread_id so the *conversation* is the unit
    # of LangGraph state, not the particular agent.
    thread_id = session_id

    result_state = await _langchain_graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": thread_id}},
    )

    return result_state["result"]
