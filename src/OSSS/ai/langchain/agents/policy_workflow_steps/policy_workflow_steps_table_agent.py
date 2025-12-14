# Auto-generated LangChain agent for QueryData mode="policy_workflow_steps"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .policy_workflow_steps_table import PolicyWorkflowStepsFilters, run_policy_workflow_steps_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.policy_workflow_steps")

class PolicyWorkflowStepsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `policy_workflow_steps`.
    """

    name = "lc.policy_workflow_steps_table"
    intent = "policy_workflow_steps"
    intent_aliases = ['policy workflow steps', 'policy_workflow_steps', 'steps in policy workflow', 'policy approval steps', 'policy review steps', 'dcg policy workflow steps', 'osss policy workflow steps']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_policy_workflow_steps_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PolicyWorkflowStepsTableAgent())
