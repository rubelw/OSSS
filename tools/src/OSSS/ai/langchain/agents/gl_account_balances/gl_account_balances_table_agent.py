# Auto-generated LangChain agent for QueryData mode="gl_account_balances"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .gl_account_balances_table import GlAccountBalancesFilters, run_gl_account_balances_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.gl_account_balances")

class GlAccountBalancesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `gl_account_balances`.
    """

    name = "lc.gl_account_balances_table"
    intent = "gl_account_balances"
    intent_aliases = ['gl account balances', 'gl_account_balances', 'general ledger balances', 'account balances', 'trial balance', 'ending balances', 'ledger balances']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_gl_account_balances_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(GlAccountBalancesTableAgent())
