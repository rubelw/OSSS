# Auto-generated LangChain agent for QueryData mode="course_prerequisites"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .course_prerequisites_table import CoursePrerequisitesFilters, run_course_prerequisites_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.course_prerequisites")

class CoursePrerequisitesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `course_prerequisites`.
    """

    name = "lc.course_prerequisites_table"
    intent = "course_prerequisites"
    intent_aliases = ['course prerequisites', 'course_prerequisites', 'course prereqs', 'prereqs for a course']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_course_prerequisites_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(CoursePrerequisitesTableAgent())
