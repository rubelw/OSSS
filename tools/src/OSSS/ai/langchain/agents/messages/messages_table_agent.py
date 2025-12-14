# Auto-generated LangChain agent for QueryData mode="messages"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .messages_table import MessagesFilters, run_messages_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.messages")

class MessagesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `messages`.
    """

    name = "lc.messages_table"
    intent = "messages"
    intent_aliases = ['messages', 'internal messages', 'osss messages', 'dcg messages', 'message threads', 'staff messages']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_messages_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MessagesTableAgent())
