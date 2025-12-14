# Auto-generated LangChain agent for QueryData mode="policy_publications"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .policy_publications_table import PolicyPublicationsFilters, run_policy_publications_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.policy_publications")

class PolicyPublicationsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `policy_publications`.
    """

    name = "lc.policy_publications_table"
    intent = "policy_publications"
    intent_aliases = ['policy publications', 'policy_publications', 'published policies', 'policy communication', 'dcg policy publications', 'osss policy publications']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_policy_publications_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PolicyPublicationsTableAgent())
