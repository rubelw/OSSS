# Auto-generated LangChain agent for QueryData mode="organizations"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .organizations_table import OrganizationsFilters, run_organizations_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.organizations")

class OrganizationsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `organizations`.
    """

    name = "lc.organizations_table"
    intent = "organizations"
    intent_aliases = ['organizations', 'orgs', 'district organizations', 'schools list', 'buildings list', 'dcg organizations', 'osss organizations']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_organizations_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(OrganizationsTableAgent())
