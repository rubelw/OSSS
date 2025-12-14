# Auto-generated LangChain agent for QueryData mode="document_versions"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .document_versions_table import DocumentVersionsFilters, run_document_versions_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.document_versions")

class DocumentVersionsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `document_versions`.
    """

    name = "lc.document_versions_table"
    intent = "document_versions"
    intent_aliases = ['document versions', 'document_versions', 'version history', 'document history']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_document_versions_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(DocumentVersionsTableAgent())
