# Auto-generated LangChain agent for QueryData mode="student_section_enrollments"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .student_section_enrollments_table import StudentSectionEnrollmentsFilters, run_student_section_enrollments_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.student_section_enrollments")

class StudentSectionEnrollmentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `student_section_enrollments`.
    """

    name = "lc.student_section_enrollments_table"
    intent = "student_section_enrollments"
    intent_aliases = ['student_section_enrollments', 'student section enrollments', 'section enrollments', 'student schedule enrollments', 'student class enrollments', 'student enrollment list', 'class enrollments', 'show section enrollments', 'list student enrollments']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_student_section_enrollments_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(StudentSectionEnrollmentsTableAgent())
