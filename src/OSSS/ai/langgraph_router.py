from __future__ import annotations

from typing import Annotated, TypedDict
from operator import add
from pathlib import Path
import logging

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import BaseMessage

from OSSS.ai.router_agent import (
    RouterAgent,  # your existing orchestrator
    RagEngine,
    IntentResolver,
    AgentDispatcher,
)
from OSSS.ai.session_store import RagSession, touch_session
from OSSS.api.routers.ai_gateway import RAGRequest  # or wherever it really lives

logger = logging.getLogger("OSSS.ai.langgraph_router")

# ---- LangGraph state schema ---------------------------------------


class OSSSState(TypedDict, total=False):
    # conversation history for LangGraph
    messages: Annotated[list[BaseMessage], add]

    # your existing request + session
    rag_request: RAGRequest
    session: RagSession

    # routing metadata
    intent_label: str | None
    action: str | None
    action_confidence: float | None
    urgency: str | None
    urgency_confidence: float | None
    tone_major: str | None
    tone_major_confidence: float | None
    tone_minor: str | None
    tone_minor_confidence: float | None
    intent_raw_model_output: str | None

    # final response payload in your current /ai/chat/rag shape
    response: dict


# Singletons reused across nodes
_intent_resolver = IntentResolver()
_agent_dispatcher = AgentDispatcher()
_rag_engine = RagEngine(
    embed_url="http://host.containers.internal:11436/v1/embeddings",
    chat_url="http://host.containers.internal:11434/v1/chat/completions",
)
_router_agent = RouterAgent(
    intent_resolver=_intent_resolver,
    agent_dispatcher=_agent_dispatcher,
    rag_engine=_rag_engine,
)


# ---- Nodes --------------------------------------------------------


def node_touch_session(state: OSSSState) -> OSSSState:
    """Keep using your existing RagSession store, but also let LangGraph checkpoint."""
    session = state["session"]
    rag = state["rag_request"]
    # Reuse your existing helper
    touch_session(session, rag)
    return {"session": session}


async def node_resolve_intent(state: OSSSState) -> OSSSState:
    rag = state["rag_request"]
    session = state["session"]
    query = rag.messages[-1].content if rag.messages else ""

    ir = await _intent_resolver.resolve(rag=rag, session=session, query=query)

    return {
        "intent_label": ir.intent,
        "action": ir.action,
        "action_confidence": ir.action_confidence,
        "urgency": ir.urgency,
        "urgency_confidence": ir.urgency_confidence,
        "tone_major": ir.tone_major,
        "tone_major_confidence": ir.tone_major_confidence,
        "tone_minor": ir.tone_minor,
        "tone_minor_confidence": ir.tone_minor_confidence,
        "intent_raw_model_output": ir.intent_raw_model_output,
    }


async def node_dispatch_or_rag(state: OSSSState) -> OSSSState:
    """This mirrors your RouterAgent.run: agent → fallback to generic RAG."""
    rag = state["rag_request"]
    session = state["session"]
    intent_label = state["intent_label"] or "general"

    action = state.get("action")
    action_confidence = state.get("action_confidence")
    urgency = state.get("urgency")
    urgency_confidence = state.get("urgency_confidence")
    tone_major = state.get("tone_major")
    tone_major_confidence = state.get("tone_major_confidence")
    tone_minor = state.get("tone_minor")
    tone_minor_confidence = state.get("tone_minor_confidence")
    intent_raw_model_output = state.get("intent_raw_model_output")

    query = rag.messages[-1].content if rag.messages else ""
    session_files: list[str] = getattr(session, "files", []) or []

    # Try specialized agent
    agent_response = await _agent_dispatcher.dispatch(
        intent_label=intent_label,
        query=query,
        rag=rag,
        session=session,
        session_files=session_files,
        action=action,
        action_confidence=action_confidence,
        urgency=urgency,
        urgency_confidence=urgency_confidence,
        tone_major=tone_major,
        tone_major_confidence=tone_major_confidence,
        tone_minor=tone_minor,
        tone_minor_confidence=tone_minor_confidence,
        intent_raw_model_output=intent_raw_model_output,
    )

    if agent_response is not None:
        logger.info("LangGraph: handled by specialized agent %s", intent_label)
        return {"response": agent_response}

    # Otherwise fall back to generic RAG
    rag_response = await _rag_engine.answer(
        rag=rag,
        session=session,
        query=query,
        intent_label=intent_label,
        session_files=session_files,
        action=action,
        action_confidence=action_confidence,
        urgency=urgency,
        urgency_confidence=urgency_confidence,
        tone_major=tone_major,
        tone_major_confidence=tone_major_confidence,
        tone_minor=tone_minor,
        tone_minor_confidence=tone_minor_confidence,
        intent_raw_model_output=intent_raw_model_output,
    )

    logger.info("LangGraph: handled by RAG fallback")
    return {"response": rag_response}


# ---- Build / compile graph ----------------------------------------

# SQLite checkpointer so LangGraph is stateful between HTTP calls
_DB_PATH = Path("/workspace/langgraph_data/osss_rag_router.db")
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)



def build_router_graph() -> StateGraph:
    g = StateGraph(OSSSState)

    g.add_node("touch_session", node_touch_session)
    g.add_node("resolve_intent", node_resolve_intent)
    g.add_node("dispatch_or_rag", node_dispatch_or_rag)

    g.add_edge(START, "touch_session")
    g.add_edge("touch_session", "resolve_intent")
    g.add_edge("resolve_intent", "dispatch_or_rag")
    g.add_edge("dispatch_or_rag", END)

    return g


# Compile once at import time with a concrete SqliteSaver checkpointer
router_graph = build_router_graph().compile()

