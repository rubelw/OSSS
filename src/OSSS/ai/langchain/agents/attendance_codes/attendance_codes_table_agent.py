# Auto-generated LangChain agent for QueryData mode="attendance_codes"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .attendance_codes_table import AttendanceCodesFilters, run_attendance_codes_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.attendance_codes")

class AttendanceCodesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `attendance_codes`.
    """

    name = "lc.attendance_codes_table"
    intent = "attendance_codes"
    intent_aliases = ['attendance codes', 'attendance_codes', 'absence codes', 'tardy codes']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_attendance_codes_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(AttendanceCodesTableAgent())
