# Auto-generated LangChain agent for QueryData mode="assignments"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .assignments_table import AssignmentsFilters, run_assignments_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.assignments")

class AssignmentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `assignments`.
    """

    name = "lc.assignments_table"
    intent = "assignments"
    intent_aliases = ['assignments', 'class assignments', 'course assignments']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_assignments_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(AssignmentsTableAgent())
