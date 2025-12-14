# Auto-generated LangChain agent for QueryData mode="policy_versions"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .policy_versions_table import PolicyVersionsFilters, run_policy_versions_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.policy_versions")

class PolicyVersionsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `policy_versions`.
    """

    name = "lc.policy_versions_table"
    intent = "policy_versions"
    intent_aliases = ['policy versions', 'policy_versions', 'versions of policies', 'policy version history', 'dcg policy versions', 'osss policy versions']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_policy_versions_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PolicyVersionsTableAgent())
