# Auto-generated LangChain agent for QueryData mode="meeting_search_index"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .meeting_search_index_table import MeetingSearchIndexFilters, run_meeting_search_index_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.meeting_search_index")

class MeetingSearchIndexTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `meeting_search_index`.
    """

    name = "lc.meeting_search_index_table"
    intent = "meeting_search_index"
    intent_aliases = ['meeting search index', 'meeting_search_index', 'search meetings index', 'meeting search metadata']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_meeting_search_index_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MeetingSearchIndexTableAgent())
