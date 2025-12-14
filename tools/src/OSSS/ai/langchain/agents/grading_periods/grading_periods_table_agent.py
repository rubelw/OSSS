# Auto-generated LangChain agent for QueryData mode="grading_periods"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .grading_periods_table import GradingPeriodsFilters, run_grading_periods_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.grading_periods")

class GradingPeriodsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `grading_periods`.
    """

    name = "lc.grading_periods_table"
    intent = "grading_periods"
    intent_aliases = ['grading periods', 'grading_periods', 'terms and quarters', 'grading terms', 'report card periods', 'marking periods']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_grading_periods_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(GradingPeriodsTableAgent())
