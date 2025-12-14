# Auto-generated LangChain agent for QueryData mode="family_portal_access"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .family_portal_access_table import FamilyPortalAccessFilters, run_family_portal_access_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.family_portal_access")

class FamilyPortalAccessTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `family_portal_access`.
    """

    name = "lc.family_portal_access_table"
    intent = "family_portal_access"
    intent_aliases = ['family portal access', 'family_portal_access', 'parent portal access', 'guardian portal access', 'portal logins', 'family accounts']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_family_portal_access_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(FamilyPortalAccessTableAgent())
