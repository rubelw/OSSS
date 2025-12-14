# Auto-generated LangChain agent for QueryData mode="user_accounts"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .user_accounts_table import UserAccountsFilters, run_user_accounts_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.user_accounts")

class UserAccountsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `user_accounts`.
    """

    name = "lc.user_accounts_table"
    intent = "user_accounts"
    intent_aliases = ['user_accounts', 'user accounts', 'login accounts', 'portal accounts', 'osss accounts', 'show user accounts']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_user_accounts_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(UserAccountsTableAgent())
