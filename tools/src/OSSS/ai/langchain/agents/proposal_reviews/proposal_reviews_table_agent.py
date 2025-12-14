# Auto-generated LangChain agent for QueryData mode="proposal_reviews"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .proposal_reviews_table import ProposalReviewsFilters, run_proposal_reviews_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.proposal_reviews")

class ProposalReviewsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `proposal_reviews`.
    """

    name = "lc.proposal_reviews_table"
    intent = "proposal_reviews"
    intent_aliases = ['proposal reviews', 'reviews of proposals', 'proposal review list', 'dcg proposal reviews', 'osss proposal reviews', 'review scores', 'grant proposal reviews']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_proposal_reviews_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ProposalReviewsTableAgent())
