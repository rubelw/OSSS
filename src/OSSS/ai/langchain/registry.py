# src/OSSS/ai/langchain/registry.py
from __future__ import annotations
from typing import Dict, Optional, Any
import logging

from .base import LangChainAgentProtocol, get_llm
from langchain_core.messages import HumanMessage

logger = logging.getLogger("OSSS.ai.langchain.registry")

_LANGCHAIN_AGENTS: Dict[str, LangChainAgentProtocol] = {}


def register_langchain_agent(agent: LangChainAgentProtocol) -> None:
    if agent.name in _LANGCHAIN_AGENTS:
        logger.warning("Overwriting LangChain agent %r", agent.name)
    _LANGCHAIN_AGENTS[agent.name] = agent


def get_langchain_agent(name: str) -> Optional[LangChainAgentProtocol]:
    logger.info("LangChain agents currently registered: %s", sorted(_LANGCHAIN_AGENTS.keys()))

    return _LANGCHAIN_AGENTS.get(name)


async def run_agent(
    message: str,
    session_id: Optional[str] = None,
    *,
    agent_name: str = "default_chat",
) -> Dict[str, Any]:

    logger.info("LangChain agents registered: %s", sorted(_LANGCHAIN_AGENTS.keys()))

    agent = get_langchain_agent(agent_name)
    if agent is None:
        logger.warning("No LangChain agent named %r; using bare LLM.", agent_name)
        llm = get_llm()
        resp = await llm.ainvoke([HumanMessage(content=message)])
        return {"reply": getattr(resp, "content", str(resp)), "agent": "bare_llm"}

    return await agent.run(message, session_id=session_id)
