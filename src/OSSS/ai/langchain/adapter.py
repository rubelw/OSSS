# OSSS/ai/langchain/adapter.py
from __future__ import annotations
from typing import Optional, Dict, Any
from OSSS.ai.agents.protocol import AgentProtocol
from OSSS.ai.langchain.base import LangChainAgentProtocol  # your existing protocol

class LangChainAgentAdapter:
    def __init__(self, agent: LangChainAgentProtocol):
        self._agent = agent
        self.name = agent.name

    async def run(self, message: str, session_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        return await self._agent.run(message, session_id=session_id)
