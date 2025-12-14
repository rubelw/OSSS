# Auto-generated LangChain agent for QueryData mode="plan_assignments"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .plan_assignments_table import PlanAssignmentsFilters, run_plan_assignments_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.plan_assignments")

class PlanAssignmentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `plan_assignments`.
    """

    name = "lc.plan_assignments_table"
    intent = "plan_assignments"
    intent_aliases = ['plan assignments', 'plan_assignments', 'assignments for plans', 'who is assigned to plans', 'dcg plan assignments', 'osss plan assignments']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_plan_assignments_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PlanAssignmentsTableAgent())
