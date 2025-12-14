# Auto-generated LangChain agent for QueryData mode="meters"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .meters_table import MetersFilters, run_meters_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.meters")

class MetersTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `meters`.
    """

    name = "lc.meters_table"
    intent = "meters"
    intent_aliases = ['meters', 'utility meters', 'energy meters', 'building meters', 'dcg meters', 'osss meters']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_meters_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MetersTableAgent())
