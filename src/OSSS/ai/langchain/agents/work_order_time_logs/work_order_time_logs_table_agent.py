# Auto-generated LangChain agent for QueryData mode="work_order_time_logs"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .work_order_time_logs_table import WorkOrderTimeLogsFilters, run_work_order_time_logs_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.work_order_time_logs")

class WorkOrderTimeLogsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `work_order_time_logs`.
    """

    name = "lc.work_order_time_logs_table"
    intent = "work_order_time_logs"
    intent_aliases = ['work order time logs', 'work_order_time_logs', 'time logs', 'work order logs', 'maintenance logs']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_work_order_time_logs_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(WorkOrderTimeLogsTableAgent())
