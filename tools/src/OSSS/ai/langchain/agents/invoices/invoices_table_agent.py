# Auto-generated LangChain agent for QueryData mode="invoices"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .invoices_table import InvoicesFilters, run_invoices_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.invoices")

class InvoicesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `invoices`.
    """

    name = "lc.invoices_table"
    intent = "invoices"
    intent_aliases = ['invoices', 'invoice list', 'vendor invoices', 'student invoices', 'district invoices']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_invoices_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(InvoicesTableAgent())
