# Auto-generated LangChain agent for QueryData mode="policy_workflows"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .policy_workflows_table import PolicyWorkflowsFilters, run_policy_workflows_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.policy_workflows")

class PolicyWorkflowsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `policy_workflows`.
    """

    name = "lc.policy_workflows_table"
    intent = "policy_workflows"
    intent_aliases = ['policy workflows', 'policy_workflows', 'policy approval workflows', 'policy review workflows', 'dcg policy workflows', 'osss policy workflows']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_policy_workflows_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PolicyWorkflowsTableAgent())
