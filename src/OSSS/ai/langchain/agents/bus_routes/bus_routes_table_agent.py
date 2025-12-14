# Auto-generated LangChain agent for QueryData mode="bus_routes"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .bus_routes_table import BusRoutesFilters, run_bus_routes_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.bus_routes")

class BusRoutesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `bus_routes`.
    """

    name = "lc.bus_routes_table"
    intent = "bus_routes"
    intent_aliases = ['bus routes', 'bus_routes', 'transportation routes']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_bus_routes_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(BusRoutesTableAgent())
