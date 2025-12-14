# Auto-generated LangChain agent for QueryData mode="meeting_documents"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .meeting_documents_table import MeetingDocumentsFilters, run_meeting_documents_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.meeting_documents")

class MeetingDocumentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `meeting_documents`.
    """

    name = "lc.meeting_documents_table"
    intent = "meeting_documents"
    intent_aliases = ['meeting documents', 'meeting_documents', 'documents attached to meetings', 'board meeting documents']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_meeting_documents_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MeetingDocumentsTableAgent())
