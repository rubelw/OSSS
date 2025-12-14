# Auto-generated LangChain agent for QueryData mode="document_notifications"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .document_notifications_table import DocumentNotificationsFilters, run_document_notifications_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.document_notifications")

class DocumentNotificationsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `document_notifications`.
    """

    name = "lc.document_notifications_table"
    intent = "document_notifications"
    intent_aliases = ['document notifications', 'document_notifications', 'who was notified', 'document acknowledgement', 'document alerts']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_document_notifications_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(DocumentNotificationsTableAgent())
