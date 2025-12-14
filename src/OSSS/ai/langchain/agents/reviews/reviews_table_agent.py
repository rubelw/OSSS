# Auto-generated LangChain agent for QueryData mode="reviews"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .reviews_table import ReviewsFilters, run_reviews_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.reviews")

class ReviewsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `reviews`.
    """

    name = "lc.reviews_table"
    intent = "reviews"
    intent_aliases = ['reviews', 'review records', 'show reviews', 'list reviews', 'feedback reviews', 'dcg reviews', 'osss reviews']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_reviews_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ReviewsTableAgent())
