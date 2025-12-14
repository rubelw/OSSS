# Auto-generated LangChain agent for QueryData mode="gl_accounts"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .gl_accounts_table import GlAccountsFilters, run_gl_accounts_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.gl_accounts")

class GlAccountsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `gl_accounts`.
    """

    name = "lc.gl_accounts_table"
    intent = "gl_accounts"
    intent_aliases = ['gl accounts', 'gl_accounts', 'general ledger accounts', 'chart of accounts', 'coa accounts', 'accounting accounts', 'financial accounts']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_gl_accounts_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(GlAccountsTableAgent())
