# Auto-generated LangChain agent for QueryData mode="payroll_runs"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .payroll_runs_table import PayrollRunsFilters, run_payroll_runs_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.payroll_runs")

class PayrollRunsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `payroll_runs`.
    """

    name = "lc.payroll_runs_table"
    intent = "payroll_runs"
    intent_aliases = ['payroll runs', 'payroll_runs', 'payroll run list', 'payroll processing runs', 'dcg payroll runs', 'osss payroll runs']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_payroll_runs_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PayrollRunsTableAgent())
