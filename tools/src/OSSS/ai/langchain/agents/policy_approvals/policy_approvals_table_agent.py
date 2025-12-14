# Auto-generated LangChain agent for QueryData mode="policy_approvals"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .policy_approvals_table import PolicyApprovalsFilters, run_policy_approvals_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.policy_approvals")

class PolicyApprovalsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `policy_approvals`.
    """

    name = "lc.policy_approvals_table"
    intent = "policy_approvals"
    intent_aliases = ['policy approvals', 'policy_approvals', 'approvals for policies', 'policy approval steps', 'policy approval records', 'dcg policy approvals', 'osss policy approvals']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_policy_approvals_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PolicyApprovalsTableAgent())
