# Auto-generated LangChain agent for QueryData mode="courses"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .courses_table import CoursesFilters, run_courses_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.courses")

class CoursesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `courses`.
    """

    name = "lc.courses_table"
    intent = "courses"
    intent_aliases = ['courses', 'course catalog', 'course list', 'available courses']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_courses_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(CoursesTableAgent())
