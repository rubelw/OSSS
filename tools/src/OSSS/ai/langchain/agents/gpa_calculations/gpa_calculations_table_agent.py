# Auto-generated LangChain agent for QueryData mode="gpa_calculations"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .gpa_calculations_table import GpaCalculationsFilters, run_gpa_calculations_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.gpa_calculations")

class GpaCalculationsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `gpa_calculations`.
    """

    name = "lc.gpa_calculations_table"
    intent = "gpa_calculations"
    intent_aliases = ['gpa calculations', 'gpa_calculations', 'calculate gpa', 'student gpa', 'weighted gpa', 'unweighted gpa', 'cumulative gpa', 'term gpa', 'gpa result']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_gpa_calculations_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(GpaCalculationsTableAgent())
