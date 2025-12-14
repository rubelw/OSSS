# Auto-generated LangChain agent for QueryData mode="part_locations"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .part_locations_table import PartLocationsFilters, run_part_locations_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.part_locations")

class PartLocationsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `part_locations`.
    """

    name = "lc.part_locations_table"
    intent = "part_locations"
    intent_aliases = ['part locations', 'part_locations', 'where parts are stored', 'inventory locations', 'stock locations', 'dcg part locations', 'osss part locations']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_part_locations_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PartLocationsTableAgent())
