# Auto-generated LangChain agent for QueryData mode="maintenance_requests"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .maintenance_requests_table import MaintenanceRequestsFilters, run_maintenance_requests_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.maintenance_requests")

class MaintenanceRequestsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `maintenance_requests`.
    """

    name = "lc.maintenance_requests_table"
    intent = "maintenance_requests"
    intent_aliases = ['maintenance requests', 'maintenance_requests', 'maintenance tickets', 'work orders', 'facility requests', 'dcg maintenance requests']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_maintenance_requests_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MaintenanceRequestsTableAgent())
