# Auto-generated LangChain agent for QueryData mode="roles"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .roles_table import RolesFilters, run_roles_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.roles")

class RolesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `roles`.
    """

    name = "lc.roles_table"
    intent = "roles"
    intent_aliases = ['roles', 'role list', 'user roles', 'permission roles', 'system roles', 'district roles', 'what roles', 'which roles', 'show roles', 'list roles']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_roles_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(RolesTableAgent())
