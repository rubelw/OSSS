# Auto-generated LangChain agent for QueryData mode="departments"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .departments_table import DepartmentsFilters, run_departments_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.departments")

class DepartmentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `departments`.
    """

    name = "lc.departments_table"
    intent = "departments"
    intent_aliases = ['departments', 'school departments', 'district departments', 'department list']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_departments_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(DepartmentsTableAgent())
