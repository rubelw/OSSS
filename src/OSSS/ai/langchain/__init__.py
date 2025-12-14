# src/OSSS/ai/langchain/__init__.py
from __future__ import annotations

from typing import Any, Dict, TypedDict, Optional
import logging
import inspect
import pkgutil
import importlib

from OSSS.ai.agents.base import AgentResult
from langgraph.graph import StateGraph, START, END

from OSSS.ai.langchain.registry import (
    register_langchain_agent,
    run_agent as registry_run_agent,
    get_langchain_agent,  # ✅ use registry for dynamic resolution
)

logger = logging.getLogger("OSSS.ai.langchain")

DEFAULT_AGENT_NAME = "lc.student_info_table"  # keep a safe fallback


# ---------------------------------------------------------------------------
# Auto-discover and register agents
# ---------------------------------------------------------------------------

def _autodiscover_and_register_agents() -> None:
    """
    Import all modules under OSSS.ai.langchain.agents and register any agent classes
    that provide:
      - .name (str)
      - async def run(self, message: str, session_id: Optional[str] = None, ...)
    Assumes agents have a no-arg constructor.
    """
    base_pkg = "OSSS.ai.langchain.agents"

    try:
        pkg = importlib.import_module(base_pkg)
    except Exception:
        logger.exception("Failed to import %s for agent autodiscovery", base_pkg)
        return

    for modinfo in pkgutil.walk_packages(pkg.__path__, prefix=f"{base_pkg}."):
        modname = modinfo.name
        try:
            module = importlib.import_module(modname)
        except Exception:
            logger.exception("Failed importing %s during agent autodiscovery", modname)
            continue

        for _, obj in inspect.getmembers(module, inspect.isclass):
            # Only consider classes defined in this module (avoid imported classes)
            if obj.__module__ != modname:
                continue

            # Must have .name
            name = getattr(obj, "name", None)
            if not isinstance(name, str) or not name.strip():
                continue

            # Must have async .run
            run_fn = getattr(obj, "run", None)
            if run_fn is None or not inspect.iscoroutinefunction(run_fn):
                continue

            # Instantiate (assumes no-arg constructor)
            try:
                instance = obj()
            except Exception:
                logger.exception("Could not instantiate agent class %s", obj)
                continue

            try:
                register_langchain_agent(instance)
                logger.info("Registered LangChain agent: %s (%s)", instance.name, modname)
            except Exception:
                logger.exception("Failed registering agent %r from %s", name, modname)


# Register agents at import time (dev reload is safe due to idempotent registry)
_autodiscover_and_register_agents()


# ---------------------------------------------------------------------------
# LangGraph state + nodes
# ---------------------------------------------------------------------------

class LangchainState(TypedDict, total=False):
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
    return {"normalized_message": normalized}


def _candidate_agent_names(intent: str) -> list[str]:
    """
    Try a few common conventions. This works great with the registry's
    dynamic normalization (lc. prefix, _table suffix stripping, etc.).
    """
    i = intent.strip()
    return [
        i,
        f"lc.{i}",
        f"{i}_table",
        f"lc.{i}_table",
        f"{i}_agent",
        f"lc.{i}_agent",
    ]


async def _node_select_agent(state: LangchainState) -> LangchainState:
    agent_name = state.get("agent_name")
    intent = state.get("intent")

    if agent_name:
        resolved = agent_name
        reason = "explicit agent_name from caller"
    elif intent:
        resolved = None
        for cand in _candidate_agent_names(intent):
            if get_langchain_agent(cand) is not None:
                resolved = cand
                reason = f"matched from intent={intent!r} via candidate={cand!r}"
                break

        if resolved is None:
            resolved = DEFAULT_AGENT_NAME
            reason = f"no agent matched intent={intent!r}; fallback to DEFAULT_AGENT_NAME"
    else:
        resolved = DEFAULT_AGENT_NAME
        reason = "no intent; fallback to DEFAULT_AGENT_NAME"

    logger.info(
        "LangGraph[langchain]._node_select_agent: session_id=%s intent=%r -> agent=%s (%s)",
        state["session_id"],
        intent,
        resolved,
        reason,
    )
    return {"agent_name": resolved}


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

    result = await registry_run_agent(
        message=normalized,
        session_id=session_id,
        agent_name=agent_name,
    )
    return {"result": result}


def _node_postprocess(state: dict) -> dict:
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

    return {**state, "reply": reply_text}


# ---------------------------------------------------------------------------
# Compile LangGraph workflow
# ---------------------------------------------------------------------------

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
# Public entry point
# ---------------------------------------------------------------------------

async def run_agent(
    message: str,
    session_id: str,
    agent_name: str | None = None,
    intent: str | None = None,
    rag: Any | None = None,
    rag_request: Any | None = None,
    **_extra: Any,
) -> Dict[str, Any]:
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

    result_state = await _langchain_graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": session_id}},
    )

    return result_state["result"]
