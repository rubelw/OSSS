# Auto-generated LangChain agent for QueryData mode="work_order_tasks"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .work_order_tasks_table import WorkOrderTasksFilters, run_work_order_tasks_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.work_order_tasks")

class WorkOrderTasksTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `work_order_tasks`.
    """

    name = "lc.work_order_tasks_table"
    intent = "work_order_tasks"
    intent_aliases = ['work_order_tasks', 'work order tasks', 'wo tasks', 'maintenance tasks', 'work order task list']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_work_order_tasks_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(WorkOrderTasksTableAgent())
