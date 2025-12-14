# Auto-generated LangChain agent for QueryData mode="paychecks"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .paychecks_table import PaychecksFilters, run_paychecks_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.paychecks")

class PaychecksTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `paychecks`.
    """

    name = "lc.paychecks_table"
    intent = "paychecks"
    intent_aliases = ['paychecks', 'pay checks', 'staff paychecks', 'employee checks', 'dcg paychecks', 'osss paychecks']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_paychecks_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PaychecksTableAgent())
