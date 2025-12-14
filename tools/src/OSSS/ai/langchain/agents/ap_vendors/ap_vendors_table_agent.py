# Auto-generated LangChain agent for QueryData mode="ap_vendors"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .ap_vendors_table import ApVendorsFilters, run_ap_vendors_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.ap_vendors")

class ApVendorsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `ap_vendors`.
    """

    name = "lc.ap_vendors_table"
    intent = "ap_vendors"
    intent_aliases = ['ap vendors', 'ap_vendors', 'accounts payable vendors', 'vendor list']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_ap_vendors_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ApVendorsTableAgent())
