# Auto-generated LangChain agent for QueryData mode="deliveries"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .deliveries_table import DeliveriesFilters, run_deliveries_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.deliveries")

class DeliveriesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `deliveries`.
    """

    name = "lc.deliveries_table"
    intent = "deliveries"
    intent_aliases = ['deliveries', 'delivery records', 'shipment deliveries', 'po deliveries']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_deliveries_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(DeliveriesTableAgent())
