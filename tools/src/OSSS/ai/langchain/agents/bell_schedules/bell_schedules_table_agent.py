# Auto-generated LangChain agent for QueryData mode="bell_schedules"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .bell_schedules_table import BellSchedulesFilters, run_bell_schedules_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.bell_schedules")

class BellSchedulesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `bell_schedules`.
    """

    name = "lc.bell_schedules_table"
    intent = "bell_schedules"
    intent_aliases = ['bell schedules', 'bell_schedules', 'daily schedule', 'period schedule']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_bell_schedules_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(BellSchedulesTableAgent())
