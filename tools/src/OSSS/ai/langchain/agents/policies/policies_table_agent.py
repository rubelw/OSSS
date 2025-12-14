# Auto-generated LangChain agent for QueryData mode="policies"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .policies_table import PoliciesFilters, run_policies_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.policies")

class PoliciesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `policies`.
    """

    name = "lc.policies_table"
    intent = "policies"
    intent_aliases = ['policies', 'district policies', 'board policies', 'dcg policies', 'osss policies', 'policy list', 'list of policies']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_policies_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PoliciesTableAgent())
