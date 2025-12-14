# Auto-generated LangChain agent for QueryData mode="payments"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .payments_table import PaymentsFilters, run_payments_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.payments")

class PaymentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `payments`.
    """

    name = "lc.payments_table"
    intent = "payments"
    intent_aliases = ['payments', 'payment records', 'payroll payments', 'staff payments', 'dcg payments', 'osss payments']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_payments_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PaymentsTableAgent())
