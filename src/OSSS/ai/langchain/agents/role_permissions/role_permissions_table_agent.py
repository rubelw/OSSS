# Auto-generated LangChain agent for QueryData mode="role_permissions"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .role_permissions_table import RolePermissionsFilters, run_role_permissions_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.role_permissions")

class RolePermissionsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `role_permissions`.
    """

    name = "lc.role_permissions_table"
    intent = "role_permissions"
    intent_aliases = ['role permissions', 'role_permissions', 'permissions by role', 'permissions for role', 'what can this role do', 'which permissions', 'list role permissions', 'show role permissions', 'role access', 'role privileges']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_role_permissions_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(RolePermissionsTableAgent())
