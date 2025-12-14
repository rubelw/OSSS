# Auto-generated LangChain agent for QueryData mode="policy_legal_refs"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .policy_legal_refs_table import PolicyLegalRefsFilters, run_policy_legal_refs_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.policy_legal_refs")

class PolicyLegalRefsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `policy_legal_refs`.
    """

    name = "lc.policy_legal_refs_table"
    intent = "policy_legal_refs"
    intent_aliases = ['policy legal refs', 'policy legal references', 'policy_legal_refs', 'legal references for policies', 'policy citations', 'legal citations for policies', 'dcg policy legal refs', 'osss policy legal refs']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_policy_legal_refs_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PolicyLegalRefsTableAgent())
