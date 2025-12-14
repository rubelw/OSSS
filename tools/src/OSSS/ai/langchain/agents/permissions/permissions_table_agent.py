# Auto-generated LangChain agent for QueryData mode="permissions"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .permissions_table import PermissionsFilters, run_permissions_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.permissions")

class PermissionsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `permissions`.
    """

    name = "lc.permissions_table"
    intent = "permissions"
    intent_aliases = ['permissions', 'access control', 'who can do what', 'acl', 'permission records', 'dcg permissions', 'osss permissions']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_permissions_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PermissionsTableAgent())
