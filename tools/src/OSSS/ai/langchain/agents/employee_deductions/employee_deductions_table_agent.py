# Auto-generated LangChain agent for QueryData mode="employee_deductions"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .employee_deductions_table import EmployeeDeductionsFilters, run_employee_deductions_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.employee_deductions")

class EmployeeDeductionsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `employee_deductions`.
    """

    name = "lc.employee_deductions_table"
    intent = "employee_deductions"
    intent_aliases = ['employee deductions', 'employee_deductions', 'payroll deductions', 'staff deductions', 'benefit deductions']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_employee_deductions_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(EmployeeDeductionsTableAgent())
