# Auto-generated LangChain agent for QueryData mode="work_order_parts"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .work_order_parts_table import WorkOrderPartsFilters, run_work_order_parts_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.work_order_parts")

class WorkOrderPartsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `work_order_parts`.
    """

    name = "lc.work_order_parts_table"
    intent = "work_order_parts"
    intent_aliases = ['work_order_parts', 'work order parts', 'wo parts', 'maintenance parts used', 'parts used on work orders']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_work_order_parts_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(WorkOrderPartsTableAgent())
