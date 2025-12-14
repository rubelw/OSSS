# Auto-generated LangChain agent for QueryData mode="assignment_categories"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .assignment_categories_table import AssignmentCategoriesFilters, run_assignment_categories_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.assignment_categories")

class AssignmentCategoriesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `assignment_categories`.
    """

    name = "lc.assignment_categories_table"
    intent = "assignment_categories"
    intent_aliases = ['assignment categories', 'assignment_categories', 'gradebook categories', 'grading categories']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_assignment_categories_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(AssignmentCategoriesTableAgent())
