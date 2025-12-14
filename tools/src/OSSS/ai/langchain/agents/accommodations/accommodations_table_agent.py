# Auto-generated LangChain agent for QueryData mode="accommodations"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .accommodations_table import AccommodationsFilters, run_accommodations_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.accommodations")

class AccommodationsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `accommodations`.
    """

    name = "lc.accommodations_table"
    intent = "accommodations"
    intent_aliases = ['accommodations', 'student accommodations', 'testing accommodations']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_accommodations_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(AccommodationsTableAgent())
