# Auto-generated LangChain agent for QueryData mode="attendances"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .attendances_table import AttendancesFilters, run_attendances_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.attendances")

class AttendancesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `attendances`.
    """

    name = "lc.attendances_table"
    intent = "attendances"
    intent_aliases = ['attendance', 'attendances', 'period attendance', 'class attendance']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_attendances_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(AttendancesTableAgent())
