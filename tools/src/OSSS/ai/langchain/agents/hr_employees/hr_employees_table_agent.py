# Auto-generated LangChain agent for QueryData mode="hr_employees"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .hr_employees_table import HrEmployeesFilters, run_hr_employees_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.hr_employees")

class HrEmployeesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `hr_employees`.
    """

    name = "lc.hr_employees_table"
    intent = "hr_employees"
    intent_aliases = ['hr employees', 'hr_employees', 'staff directory', 'employee directory', 'employee list']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_hr_employees_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(HrEmployeesTableAgent())
