# Auto-generated LangChain agent for QueryData mode="attendance_events"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .attendance_events_table import AttendanceEventsFilters, run_attendance_events_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.attendance_events")

class AttendanceEventsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `attendance_events`.
    """

    name = "lc.attendance_events_table"
    intent = "attendance_events"
    intent_aliases = ['attendance events', 'attendance_events', 'check in', 'check out']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_attendance_events_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(AttendanceEventsTableAgent())
