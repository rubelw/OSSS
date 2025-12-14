# src/OSSS/ai/langchain/__init__.py
from __future__ import annotations

from typing import Any, Dict, TypedDict, Optional
import logging
from OSSS.ai.agents.base import AgentResult

from langgraph.graph import StateGraph, START, END

from OSSS.ai.langchain.agents.student_info.student_info_table_agent import StudentInfoTableAgent
from OSSS.ai.langchain.agents.staff_info.staff_info_table_agent import StaffInfoTableAgent

from OSSS.ai.langchain.registry import (
    register_langchain_agent,
    run_agent as registry_run_agent,
)

logger = logging.getLogger("OSSS.ai.langchain")

# ---------------------------------------------------------------------------
# Intent → LangChain agent name mapping
# ---------------------------------------------------------------------------

# NOTE: dict keys must be unique. Your previous file had "langchain_agent" twice,
# which meant the first mapping was overwritten silently.
INTENT_TO_LC_AGENT: dict[str, str] = {
    # bridge from old behavior: generic "langchain_agent" goes to student_info_table
    "langchain_agent": "lc.student_info_table",

    # student intents
    "student_info": "lc.student_info_table",

    # staff intents
    "staff_info": "lc.staff_info_table",
    "staff_directory": "lc.staff_info_table",

    # add more as you build them...
    # "students_missing_assignments": "lc.students_missing_assignments",
}

DEFAULT_AGENT_NAME = "lc.student_info_table"

# ---------------------------------------------------------------------------
# Register concrete agents with the registry
# ---------------------------------------------------------------------------

register_langchain_agent(StudentInfoTableAgent())
register_langchain_agent(StaffInfoTableAgent())

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
    raw = state["raw_message"]
    normalized = " ".join(raw.strip().split())

    logger.debug(
        "LangGraph[langchain]._node_preprocess: session_id=%s raw=%r normalized=%r",
        state["session_id"],
        raw,
        normalized,
    )

    return {
        "normalized_message": normalized,
    }


async def _node_select_agent(state: LangchainState) -> LangchainState:
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

    return {
        "agent_name": resolved,
    }


async def _node_run_registry_agent(state: LangchainState) -> LangchainState:
    normalized = state.get("normalized_message") or state["raw_message"]
    session_id = state["session_id"]
    agent_name = state["agent_name"] or DEFAULT_AGENT_NAME

    logger.info(
        "LangGraph[langchain]._node_run_registry_agent: session_id=%s agent_name=%s message=%r",
        session_id,
        agent_name,
        normalized,
    )

    # If your registry supports passing intent/extra context, this is where you’d add it.
    result = await registry_run_agent(
        message=normalized,
        session_id=session_id,
        agent_name=agent_name,
    )

    return {
        "result": result,
    }


def _node_postprocess(state: dict) -> dict:
    """
    LangGraph node: normalize whatever the agent produced into state["reply"].

    This node is invoked with ONLY `state` (not `(state, result)`), so extract
    the latest agent output from the state itself.
    """

    # Depending on how your graph stores it, try a few common keys
    result: Any = (
        state.get("agent_result")
        or state.get("result")
        or state.get("output")
        or state.get("final")
    )

    if isinstance(result, AgentResult):
        reply_text = result.answer_text
    elif isinstance(result, dict):
        reply_text = (
            result.get("reply")
            or result.get("output")
            or result.get("answer_text")
            or ""
        )
        if not reply_text:
            reply_text = str(result)
    elif result is None:
        reply_text = ""
    else:
        reply_text = str(result)

    # Return updated state
    return {
        **state,
        "reply": reply_text,
    }

# ---------------------------------------------------------------------------
# Compile LangGraph workflow with SQLite checkpointer
# ---------------------------------------------------------------------------

_langgraph_db_path = "/workspace/langgraph_data/osss_langgraph.db"


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

_langchain_graph = _langchain_builder.compile()

# ---------------------------------------------------------------------------
# Public entry point used by RouterAgent and /ai/langchain/chat
# ---------------------------------------------------------------------------

async def run_agent(
    message: str,
    session_id: str,
    agent_name: str | None = None,
    intent: str | None = None,
    rag: Any | None = None,          # ✅ accept it (RouterAgent passes it)
    rag_request: Any | None = None,  # ✅ accept alt name too (future-proof)
    **_extra: Any,                   # ✅ swallow anything else safely
) -> Dict[str, Any]:
    """
    Single entry-point used by RouterAgent and /ai/langchain/chat.

    `rag` / `rag_request` are accepted for compatibility with callers that pass
    the full RAG request payload/context. This module does not currently use them,
    but accepting them prevents 500s when upstream adds new kwargs.
    """
    logger.info(
        "LangChain.run_agent (via LangGraph) called: session_id=%s agent_name=%s intent=%s message=%r rag=%s",
        session_id,
        agent_name,
        intent,
        message,
        type(rag).__name__ if rag is not None else None,
    )

    initial_state: LangchainState = {
        "raw_message": message,
        "session_id": session_id,
        "agent_name": agent_name,
        "intent": intent,
    }

    thread_id = session_id

    result_state = await _langchain_graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": thread_id}},
    )

    return result_state["result"]
