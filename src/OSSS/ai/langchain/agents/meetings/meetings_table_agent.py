# Auto-generated LangChain agent for QueryData mode="meetings"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .meetings_table import MeetingsFilters, run_meetings_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.meetings")

class MeetingsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `meetings`.
    """

    name = "lc.meetings_table"
    intent = "meetings"
    intent_aliases = ['meetings', 'board meetings', 'school board meetings', 'committee meetings', 'dcg meetings', 'osss meetings']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_meetings_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MeetingsTableAgent())
