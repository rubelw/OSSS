# Auto-generated LangChain agent for QueryData mode="department_position_index"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .department_position_index_table import DepartmentPositionIndexFilters, run_department_position_index_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.department_position_index")

class DepartmentPositionIndexTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `department_position_index`.
    """

    name = "lc.department_position_index_table"
    intent = "department_position_index"
    intent_aliases = ['department position index', 'department_position_index', 'department staffing index', 'fte by department', 'positions by department']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_department_position_index_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(DepartmentPositionIndexTableAgent())
