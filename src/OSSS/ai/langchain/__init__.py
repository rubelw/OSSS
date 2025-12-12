# src/OSSS/ai/langchain/__init__.py
from __future__ import annotations

from typing import TypedDict, Annotated, Any
from operator import add
import logging
import inspect

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage

from OSSS.ai.session_store import RagSession
from OSSS.ai.langchain.agents.student_info.student_info_table_agent import StudentInfoTableAgent

logger = logging.getLogger("OSSS.ai.langchain")

# -------------------------------------------------------------------
# Simple local LC agent registry
# -------------------------------------------------------------------


def get_agent_for_name(agent_name: str):
    """
    Minimal registry for LangChain-style agents used via LangGraph.

    Expand this as you add more LC agents. For now we only support
    the student info table agent.
    """
    if agent_name == "lc.student_info_table":
        return StudentInfoTableAgent()

    raise ValueError(f"Unknown LangChain agent_name={agent_name!r}")


# -------------------------------------------------------------------
# LangChain graph state type
# -------------------------------------------------------------------


class LangChainState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add]
    session_id: str
    agent_name: str
    # We keep RAGRequest as Any to avoid circular imports; we only
    # need its .messages attribute at runtime.
    rag_request: Any
    session: RagSession
    # where we stash the agent result
    result: dict


# -------------------------------------------------------------------
# Helper: build kwargs for an agent method based on its signature
# -------------------------------------------------------------------


def _build_agent_call_kwargs(
    fn: Any,
    *,
    query: str,
    rag: Any,
    session: RagSession,
) -> dict:
    """
    Inspect the function signature and only pass arguments it expects.

    This lets you have agents with signatures like:

        run(self, rag, session)
        run(self, request, session)
        run(self, query, rag, session)
        run(self, request)

    without forcing everyone to accept `query=..., rag=..., session=...`.
    """
    sig = inspect.signature(fn)
    call_kwargs: dict[str, Any] = {}

    for name, param in sig.parameters.items():
        # For bound methods, "self" is usually not present; this is just a guard.
        if name == "self":
            continue

        # Map typical names for the natural-language query
        if name in {"query", "question", "text", "prompt", "message"}:
            call_kwargs[name] = query
        # Map typical names for the RAG request object
        elif name in {"rag", "request", "rag_request", "rag_request_obj"}:
            call_kwargs[name] = rag
        # Map typical names for the session / context
        elif name in {"session", "rag_session", "db_session"}:
            call_kwargs[name] = session
        else:
            # Leave anything else alone; if it's required with no default,
            # we will detect that below and raise a nicer error.
            continue

    # Check for required params we couldn't fill
    missing_required = [
        name
        for name, param in sig.parameters.items()
        if name != "self"
        and param.default is inspect._empty
        and name not in call_kwargs
    ]

    if missing_required:
        raise TypeError(
            f"Cannot call agent method {fn!r}: missing required parameters "
            f"{missing_required!r}. Available context params: "
            f"query, rag_request, session."
        )

    return call_kwargs


# -------------------------------------------------------------------
# Nodes
# -------------------------------------------------------------------


async def node_run_agent(state: LangChainState) -> LangChainState:
    """Single node that runs the chosen LangChain agent."""
    session_id = state["session_id"]
    agent_name = state["agent_name"]
    rag = state["rag_request"]
    session = state["session"]

    # Your own registry / factory for building LC agents
    agent = get_agent_for_name(agent_name)

    # The natural language query; adapt if you use a different source
    query = ""
    try:
        messages = getattr(rag, "messages", None) or []
        if messages:
            last = messages[-1]
            query = getattr(last, "content", "") or ""
    except Exception:
        logger.exception(
            "LangChain.node_run_agent: failed to extract query from rag.messages; "
            "defaulting to empty string"
        )

    logger.info(
        "LangChain.run_agent (via LangGraph) called: "
        "session_id=%s agent_name=%s message=%r",
        session_id,
        agent_name,
        query,
    )

    # --- Call the agent, supporting both async & sync APIs --------------
    result_payload: dict | Any

    # 1) Preferred async method, if present
    if hasattr(agent, "arun") and callable(getattr(agent, "arun")):
        arun_fn = getattr(agent, "arun")
        call_kwargs = _build_agent_call_kwargs(
            arun_fn,
            query=query,
            rag=rag,
            session=session,
        )
        result_payload = await arun_fn(**call_kwargs)

    # 2) Fallback to .run(...)
    elif hasattr(agent, "run") and callable(getattr(agent, "run")):
        run_fn = getattr(agent, "run")
        call_kwargs = _build_agent_call_kwargs(
            run_fn,
            query=query,
            rag=rag,
            session=session,
        )

        if inspect.iscoroutinefunction(run_fn):
            # Async run(...)
            result_payload = await run_fn(**call_kwargs)
        else:
            # Sync run(...). If this gets heavy we can later wrap in a thread.
            result_payload = run_fn(**call_kwargs)
    else:
        raise AttributeError(
            f"LangChain agent {agent_name!r} has neither 'arun' nor 'run' method"
        )

    return {"result": result_payload}


# -------------------------------------------------------------------
# LangGraph checkpointer for LangChain graph (in-memory)
# -------------------------------------------------------------------

_langchain_checkpointer = MemorySaver()


def build_langchain_graph() -> StateGraph:
    g = StateGraph(LangChainState)

    g.add_node("run_agent", node_run_agent)

    g.add_edge(START, "run_agent")
    g.add_edge("run_agent", END)

    return g


# Compile once at import time with the checkpointer instance
_langchain_graph = build_langchain_graph().compile(
    checkpointer=_langchain_checkpointer
)

# -------------------------------------------------------------------
# Mapping from intents to LangChain agent names
# -------------------------------------------------------------------

INTENT_TO_LC_AGENT: dict[str, str] = {
    # You can expand this mapping as needed
    "student_info": "lc.student_info_table",
}


# -------------------------------------------------------------------
# Public entrypoint used by RouterAgent
# -------------------------------------------------------------------


async def run_agent(
    *,
    session_id: str,
    agent_name: str,
    rag: Any,
    session: RagSession,
    message: str | None = None,
) -> dict:
    """
    This is what RouterAgent calls when it wants to invoke a LangChain agent
    via LangGraph.

    The `message` argument is currently unused here because we re-derive the
    query from `rag.messages`, but we keep it in the signature so
    RouterAgent can pass it without errors.
    """
    # Initial graph state
    initial_state: LangChainState = {
        "session_id": session_id,
        "agent_name": agent_name,
        "rag_request": rag,
        "session": session,
        # if you want messages in this graph, pass them here:
        # "messages": [...],
    }

    # Use a thread_id / checkpoint namespace keyed on session & agent
    thread_id = f"{session_id}:{agent_name}"

    # For newer langgraph versions, the thread_id is passed via "configurable"
    result_state = await _langchain_graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": thread_id}},
    )

    return result_state.get("result", {})
