# Auto-generated LangChain agent for QueryData mode="move_orders"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .move_orders_table import MoveOrdersFilters, run_move_orders_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.move_orders")

class MoveOrdersTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `move_orders`.
    """

    name = "lc.move_orders_table"
    intent = "move_orders"
    intent_aliases = ['move orders', 'move_orders', 'inventory move orders', 'transfer orders', 'room move orders', 'dcg move orders']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_move_orders_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MoveOrdersTableAgent())
