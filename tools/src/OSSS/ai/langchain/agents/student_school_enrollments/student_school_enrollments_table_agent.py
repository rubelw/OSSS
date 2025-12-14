# Auto-generated LangChain agent for QueryData mode="student_school_enrollments"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .student_school_enrollments_table import StudentSchoolEnrollmentsFilters, run_student_school_enrollments_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.student_school_enrollments")

class StudentSchoolEnrollmentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `student_school_enrollments`.
    """

    name = "lc.student_school_enrollments_table"
    intent = "student_school_enrollments"
    intent_aliases = ['student_school_enrollments', 'student school enrollments', 'school enrollments', 'student school enrollment list', 'student enrollment by school', 'student building enrollments', 'school-level student enrollments', 'show student school enrollments', 'list student school enrollments']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_student_school_enrollments_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(StudentSchoolEnrollmentsTableAgent())
