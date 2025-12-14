# src/OSSS/ai/langchain/registry.py
from __future__ import annotations

from typing import Dict, Optional, Any
import logging

from .base import LangChainAgentProtocol, get_llm
from langchain_core.messages import HumanMessage

logger = logging.getLogger("OSSS.ai.langchain.registry")

_LANGCHAIN_AGENTS: Dict[str, LangChainAgentProtocol] = {}


# ---------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------

def register_langchain_agent(name_or_agent, agent=None):
    """
    Supports BOTH:
      register_langchain_agent("lc.staff_info_table", agent)
      register_langchain_agent(agent)  # agent must define .name
    """

    # Backward compatibility: called with just the agent
    if agent is None:
        agent = name_or_agent
        try:
            name = agent.name
        except AttributeError:
            raise TypeError(
                "register_langchain_agent(agent) requires agent.name to be set"
            )
    else:
        name = name_or_agent

    existing = _LANGCHAIN_AGENTS.get(name)

    # Idempotent reload: same object or same class → ignore
    if existing is agent or (
        existing is not None
        and existing.__class__ is agent.__class__
    ):
        return

    if existing is not None:
        logger.warning("Overwriting LangChain agent '%s'", name)

    _LANGCHAIN_AGENTS[name] = agent


# ---------------------------------------------------------------------
# Lookup (dynamic aliases)
# ---------------------------------------------------------------------

def _normalize_agent_key(key: str) -> str:
    """
    Normalize intent / agent names so we don't need hardcoded aliases.
    """
    k = key.lower().strip()

    # Remove common prefixes/suffixes
    if k.startswith("lc."):
        k = k[3:]
    for suffix in ("_table", "_agent"):
        if k.endswith(suffix):
            k = k[: -len(suffix)]

    return k


def get_langchain_agent(intent: str | None):
    if not intent:
        return None

    intent_norm = _normalize_agent_key(intent)

    logger.info(
        "LangChain agent lookup: intent=%s normalized=%s",
        intent,
        intent_norm,
    )

    # 1) Exact name match
    agent = _LANGCHAIN_AGENTS.get(intent)
    if agent:
        return agent

    # 2) Normalized match
    for name, agent in _LANGCHAIN_AGENTS.items():
        if _normalize_agent_key(name) == intent_norm:
            return agent

    return None


# ---------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------

async def run_agent(
    message: str,
    session_id: Optional[str] = None,
    *,
    agent_name: str = "default_chat",
) -> Dict[str, Any]:

    logger.info(
        "LangChain agents registered: %s",
        sorted(_LANGCHAIN_AGENTS.keys()),
    )

    agent = get_langchain_agent(agent_name)
    if agent is None:
        logger.warning(
            "No LangChain agent matched '%s'; using bare LLM.",
            agent_name,
        )
        llm = get_llm()
        resp = await llm.ainvoke([HumanMessage(content=message)])
        return {
            "reply": getattr(resp, "content", str(resp)),
            "agent": "bare_llm",
        }

    return await agent.run(message, session_id=session_id)
