# Auto-generated LangChain agent for QueryData mode="review_requests"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .review_requests_table import ReviewRequestsFilters, run_review_requests_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.review_requests")

class ReviewRequestsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `review_requests`.
    """

    name = "lc.review_requests_table"
    intent = "review_requests"
    intent_aliases = ['review requests', 'review_requests', 'pending review requests', 'requests for review', 'policy review requests', 'proposal review requests', 'document review requests']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_review_requests_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ReviewRequestsTableAgent())
