# Auto-generated LangChain agent for QueryData mode="bus_stop_times"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .bus_stop_times_table import BusStopTimesFilters, run_bus_stop_times_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.bus_stop_times")

class BusStopTimesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `bus_stop_times`.
    """

    name = "lc.bus_stop_times_table"
    intent = "bus_stop_times"
    intent_aliases = ['bus stop times', 'bus_stop_times', 'bus schedule', 'transportation schedule']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_bus_stop_times_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(BusStopTimesTableAgent())
