# Auto-generated LangChain agent for QueryData mode="pay_periods"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .pay_periods_table import PayPeriodsFilters, run_pay_periods_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.pay_periods")

class PayPeriodsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `pay_periods`.
    """

    name = "lc.pay_periods_table"
    intent = "pay_periods"
    intent_aliases = ['pay periods', 'pay_periods', 'payroll periods', 'district pay periods', 'dcg pay periods', 'osss pay periods']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_pay_periods_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PayPeriodsTableAgent())
