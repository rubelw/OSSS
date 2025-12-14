# Auto-generated LangChain agent for QueryData mode="documents"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .documents_table import DocumentsFilters, run_documents_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.documents")

class DocumentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `documents`.
    """

    name = "lc.documents_table"
    intent = "documents"
    intent_aliases = ['documents', 'dcg documents', 'district documents', 'school documents', 'policy documents', 'handbooks']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_documents_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(DocumentsTableAgent())
