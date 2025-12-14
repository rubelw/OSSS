# Auto-generated LangChain agent for QueryData mode="document_permissions"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .document_permissions_table import DocumentPermissionsFilters, run_document_permissions_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.document_permissions")

class DocumentPermissionsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `document_permissions`.
    """

    name = "lc.document_permissions_table"
    intent = "document_permissions"
    intent_aliases = ['document permissions', 'document_permissions', 'who can see this document', 'document access', 'document sharing']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_document_permissions_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(DocumentPermissionsTableAgent())
