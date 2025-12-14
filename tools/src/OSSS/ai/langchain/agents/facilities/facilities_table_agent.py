# Auto-generated LangChain agent for QueryData mode="facilities"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .facilities_table import FacilitiesFilters, run_facilities_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.facilities")

class FacilitiesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `facilities`.
    """

    name = "lc.facilities_table"
    intent = "facilities"
    intent_aliases = ['facilities', 'school facilities', 'district facilities', 'buildings', 'campus buildings', 'facility list']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_facilities_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(FacilitiesTableAgent())
