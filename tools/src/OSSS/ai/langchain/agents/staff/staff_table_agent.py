# Auto-generated LangChain agent for QueryData mode="staff"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .staff_table import StaffFilters, run_staff_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.staff")

class StaffTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `staff`.
    """

    name = "lc.staff_table"
    intent = "staff"
    intent_aliases = ['staff', 'staff list', 'staff directory', 'employee directory', 'teacher list', 'show staff', 'show staff directory']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_staff_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(StaffTableAgent())
