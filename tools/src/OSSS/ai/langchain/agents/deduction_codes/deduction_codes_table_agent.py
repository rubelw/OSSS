# Auto-generated LangChain agent for QueryData mode="deduction_codes"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .deduction_codes_table import DeductionCodesFilters, run_deduction_codes_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.deduction_codes")

class DeductionCodesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `deduction_codes`.
    """

    name = "lc.deduction_codes_table"
    intent = "deduction_codes"
    intent_aliases = ['deduction codes', 'deduction_codes', 'payroll deduction codes', 'benefit codes', 'garnishment codes']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_deduction_codes_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(DeductionCodesTableAgent())
