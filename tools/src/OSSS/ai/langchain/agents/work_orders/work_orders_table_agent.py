# Auto-generated LangChain agent for QueryData mode="work_orders"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .work_orders_table import WorkOrdersFilters, run_work_orders_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.work_orders")

class WorkOrdersTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `work_orders`.
    """

    name = "lc.work_orders_table"
    intent = "work_orders"
    intent_aliases = ['work_orders', 'work orders', 'maintenance work orders', 'maintenance tickets', 'wo list']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_work_orders_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(WorkOrdersTableAgent())
