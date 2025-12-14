# Auto-generated LangChain agent for QueryData mode="orders"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .orders_table import OrdersFilters, run_orders_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.orders")

class OrdersTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `orders`.
    """

    name = "lc.orders_table"
    intent = "orders"
    intent_aliases = ['orders', 'purchase orders', 'work orders', 'order list', 'dcg orders', 'osss orders']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_orders_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(OrdersTableAgent())
