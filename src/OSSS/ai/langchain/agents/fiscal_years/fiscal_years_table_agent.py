# Auto-generated LangChain agent for QueryData mode="fiscal_years"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .fiscal_years_table import FiscalYearsFilters, run_fiscal_years_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.fiscal_years")

class FiscalYearsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `fiscal_years`.
    """

    name = "lc.fiscal_years_table"
    intent = "fiscal_years"
    intent_aliases = ['fiscal years', 'fiscal_years', 'finance years', 'budget years', 'accounting years']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_fiscal_years_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(FiscalYearsTableAgent())
