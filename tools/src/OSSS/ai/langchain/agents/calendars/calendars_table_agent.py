# Auto-generated LangChain agent for QueryData mode="calendars"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .calendars_table import CalendarsFilters, run_calendars_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.calendars")

class CalendarsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `calendars`.
    """

    name = "lc.calendars_table"
    intent = "calendars"
    intent_aliases = ['calendars', 'school calendars', 'district calendars']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_calendars_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(CalendarsTableAgent())
