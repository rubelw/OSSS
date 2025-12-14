# Auto-generated LangChain agent for QueryData mode="votes"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .votes_table import VotesFilters, run_votes_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.votes")

class VotesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `votes`.
    """

    name = "lc.votes_table"
    intent = "votes"
    intent_aliases = ['votes', 'vote records', 'voting records', 'ballot votes']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_votes_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(VotesTableAgent())
