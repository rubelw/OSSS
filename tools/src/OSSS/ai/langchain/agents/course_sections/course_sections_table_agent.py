# Auto-generated LangChain agent for QueryData mode="course_sections"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .course_sections_table import CourseSectionsFilters, run_course_sections_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.course_sections")

class CourseSectionsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `course_sections`.
    """

    name = "lc.course_sections_table"
    intent = "course_sections"
    intent_aliases = ['course sections', 'course_sections', 'class sections', 'sections for a course']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_course_sections_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(CourseSectionsTableAgent())
