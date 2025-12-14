# Auto-generated LangChain agent for QueryData mode="review_rounds"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .review_rounds_table import ReviewRoundsFilters, run_review_rounds_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.review_rounds")

class ReviewRoundsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `review_rounds`.
    """

    name = "lc.review_rounds_table"
    intent = "review_rounds"
    intent_aliases = ['review rounds', 'review_rounds', 'approval rounds', 'policy review rounds', 'proposal review rounds', 'evaluation rounds']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_review_rounds_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ReviewRoundsTableAgent())
