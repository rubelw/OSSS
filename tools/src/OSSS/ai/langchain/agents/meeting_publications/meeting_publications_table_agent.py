# Auto-generated LangChain agent for QueryData mode="meeting_publications"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .meeting_publications_table import MeetingPublicationsFilters, run_meeting_publications_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.meeting_publications")

class MeetingPublicationsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `meeting_publications`.
    """

    name = "lc.meeting_publications_table"
    intent = "meeting_publications"
    intent_aliases = ['meeting publications', 'meeting_publications', 'board meeting publications', 'published meetings', 'dcg meeting publications']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_meeting_publications_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MeetingPublicationsTableAgent())
