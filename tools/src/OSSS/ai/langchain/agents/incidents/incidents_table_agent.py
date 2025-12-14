# Auto-generated LangChain agent for QueryData mode="incidents"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .incidents_table import IncidentsFilters, run_incidents_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.incidents")

class IncidentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `incidents`.
    """

    name = "lc.incidents_table"
    intent = "incidents"
    intent_aliases = ['incidents', 'discipline incidents', 'behavior incidents', 'student incidents', 'incident log']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_incidents_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(IncidentsTableAgent())
