# Auto-generated LangChain agent for QueryData mode="message_recipients"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .message_recipients_table import MessageRecipientsFilters, run_message_recipients_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.message_recipients")

class MessageRecipientsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `message_recipients`.
    """

    name = "lc.message_recipients_table"
    intent = "message_recipients"
    intent_aliases = ['message recipients', 'message_recipients', 'who got messages', 'notification recipients', 'dcg message recipients', 'osss message recipients']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_message_recipients_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MessageRecipientsTableAgent())
