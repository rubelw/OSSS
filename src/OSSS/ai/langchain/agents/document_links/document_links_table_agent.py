# Auto-generated LangChain agent for QueryData mode="document_links"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .document_links_table import DocumentLinksFilters, run_document_links_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.document_links")

class DocumentLinksTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `document_links`.
    """

    name = "lc.document_links_table"
    intent = "document_links"
    intent_aliases = ['document links', 'document_links', 'related documents', 'document relationships']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_document_links_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(DocumentLinksTableAgent())
