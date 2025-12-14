# Auto-generated LangChain agent for QueryData mode="users"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .users_table import UsersFilters, run_users_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.users")

class UsersTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `users`.
    """

    name = "lc.users_table"
    intent = "users"
    intent_aliases = ['users', 'user accounts', 'user list', 'system users', 'application users', 'auth users', 'registered users', 'login accounts']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_users_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(UsersTableAgent())
