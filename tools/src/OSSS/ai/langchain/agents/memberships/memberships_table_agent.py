# Auto-generated LangChain agent for QueryData mode="memberships"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .memberships_table import MembershipsFilters, run_memberships_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.memberships")

class MembershipsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `memberships`.
    """

    name = "lc.memberships_table"
    intent = "memberships"
    intent_aliases = ['memberships', 'group memberships', 'committee memberships', 'board memberships', 'dcg memberships', 'osss memberships']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_memberships_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MembershipsTableAgent())
