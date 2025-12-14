# Auto-generated LangChain agent for QueryData mode="fiscal_periods"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .fiscal_periods_table import FiscalPeriodsFilters, run_fiscal_periods_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.fiscal_periods")

class FiscalPeriodsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `fiscal_periods`.
    """

    name = "lc.fiscal_periods_table"
    intent = "fiscal_periods"
    intent_aliases = ['fiscal periods', 'fiscal_periods', 'accounting periods', 'finance periods', 'budget periods', 'period list']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_fiscal_periods_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(FiscalPeriodsTableAgent())
