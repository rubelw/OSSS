# Auto-generated LangChain agent for QueryData mode="proposal_documents"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .proposal_documents_table import ProposalDocumentsFilters, run_proposal_documents_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.proposal_documents")

class ProposalDocumentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `proposal_documents`.
    """

    name = "lc.proposal_documents_table"
    intent = "proposal_documents"
    intent_aliases = ['proposal documents', 'proposal document list', 'documents for proposals', 'dcg proposal documents', 'osss proposal documents', 'grant proposal documents', 'attached proposal documents']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_proposal_documents_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ProposalDocumentsTableAgent())
