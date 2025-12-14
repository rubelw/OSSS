# Auto-generated LangChain agent for QueryData mode="employee_earnings"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .employee_earnings_table import EmployeeEarningsFilters, run_employee_earnings_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.employee_earnings")

class EmployeeEarningsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `employee_earnings`.
    """

    name = "lc.employee_earnings_table"
    intent = "employee_earnings"
    intent_aliases = ['employee earnings', 'employee_earnings', 'payroll earnings', 'staff earnings', 'salary earnings']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_employee_earnings_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(EmployeeEarningsTableAgent())
