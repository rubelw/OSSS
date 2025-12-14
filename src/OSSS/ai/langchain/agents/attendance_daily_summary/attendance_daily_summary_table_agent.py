# Auto-generated LangChain agent for QueryData mode="attendance_daily_summary"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .attendance_daily_summary_table import AttendanceDailySummaryFilters, run_attendance_daily_summary_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.attendance_daily_summary")

class AttendanceDailySummaryTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `attendance_daily_summary`.
    """

    name = "lc.attendance_daily_summary_table"
    intent = "attendance_daily_summary"
    intent_aliases = ['attendance daily summary', 'attendance_daily_summary', 'daily attendance summary', 'attendance rate']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_attendance_daily_summary_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(AttendanceDailySummaryTableAgent())
