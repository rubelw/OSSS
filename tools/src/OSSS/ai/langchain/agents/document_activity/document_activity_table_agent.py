# Auto-generated LangChain agent for QueryData mode="document_activity"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .document_activity_table import DocumentActivityFilters, run_document_activity_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.document_activity")

class DocumentActivityTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `document_activity`.
    """

    name = "lc.document_activity_table"
    intent = "document_activity"
    intent_aliases = ['document activity', 'document_activity', 'document audit log', 'document history', 'who viewed a document', 'who edited a document']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_document_activity_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(DocumentActivityTableAgent())
