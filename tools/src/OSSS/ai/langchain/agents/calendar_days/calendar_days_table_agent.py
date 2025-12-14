# Auto-generated LangChain agent for QueryData mode="calendar_days"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .calendar_days_table import CalendarDaysFilters, run_calendar_days_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.calendar_days")

class CalendarDaysTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `calendar_days`.
    """

    name = "lc.calendar_days_table"
    intent = "calendar_days"
    intent_aliases = ['calendar days', 'calendar_days', 'instructional days', 'school days']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_calendar_days_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(CalendarDaysTableAgent())
