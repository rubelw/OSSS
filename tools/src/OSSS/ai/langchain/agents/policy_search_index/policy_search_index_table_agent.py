# Auto-generated LangChain agent for QueryData mode="policy_search_index"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .policy_search_index_table import PolicySearchIndexFilters, run_policy_search_index_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.policy_search_index")

class PolicySearchIndexTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `policy_search_index`.
    """

    name = "lc.policy_search_index_table"
    intent = "policy_search_index"
    intent_aliases = ['policy search index', 'policy_search_index', 'searchable policies', 'policy search metadata', 'dcg policy search index', 'osss policy search index']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_policy_search_index_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PolicySearchIndexTableAgent())
