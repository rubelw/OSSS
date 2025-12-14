# Auto-generated LangChain agent for QueryData mode="vendors"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .vendors_table import VendorsFilters, run_vendors_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.vendors")

class VendorsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `vendors`.
    """

    name = "lc.vendors_table"
    intent = "vendors"
    intent_aliases = ['vendors', 'vendor list', 'vendor records', 'supplier', 'suppliers', 'approved vendors']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_vendors_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(VendorsTableAgent())
