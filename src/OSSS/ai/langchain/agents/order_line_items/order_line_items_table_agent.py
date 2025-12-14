# Auto-generated LangChain agent for QueryData mode="order_line_items"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .order_line_items_table import OrderLineItemsFilters, run_order_line_items_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.order_line_items")

class OrderLineItemsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `order_line_items`.
    """

    name = "lc.order_line_items_table"
    intent = "order_line_items"
    intent_aliases = ['order_line_items', 'order line items', 'order details', 'line items', 'dcg order items', 'osss order items']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_order_line_items_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(OrderLineItemsTableAgent())
