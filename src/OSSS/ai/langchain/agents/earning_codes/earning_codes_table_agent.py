# Auto-generated LangChain agent for QueryData mode="earning_codes"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .earning_codes_table import EarningCodesFilters, run_earning_codes_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.earning_codes")

class EarningCodesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `earning_codes`.
    """

    name = "lc.earning_codes_table"
    intent = "earning_codes"
    intent_aliases = ['earning codes', 'earning_codes', 'payroll earning codes', 'pay codes', 'payroll codes']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_earning_codes_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(EarningCodesTableAgent())
