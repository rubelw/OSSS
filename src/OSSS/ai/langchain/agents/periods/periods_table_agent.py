# Auto-generated LangChain agent for QueryData mode="periods"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .periods_table import PeriodsFilters, run_periods_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.periods")

class PeriodsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `periods`.
    """

    name = "lc.periods_table"
    intent = "periods"
    intent_aliases = ['periods', 'reporting periods', 'term periods', 'grading periods', 'dcg periods', 'osss periods']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_periods_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PeriodsTableAgent())
