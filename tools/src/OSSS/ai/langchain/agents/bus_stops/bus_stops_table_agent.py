# Auto-generated LangChain agent for QueryData mode="bus_stops"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .bus_stops_table import BusStopsFilters, run_bus_stops_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.bus_stops")

class BusStopsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `bus_stops`.
    """

    name = "lc.bus_stops_table"
    intent = "bus_stops"
    intent_aliases = ['bus stops', 'bus_stops', 'transportation stops']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_bus_stops_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(BusStopsTableAgent())
