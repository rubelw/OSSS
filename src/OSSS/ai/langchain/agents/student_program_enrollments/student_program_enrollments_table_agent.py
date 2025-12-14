# Auto-generated LangChain agent for QueryData mode="student_program_enrollments"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .student_program_enrollments_table import StudentProgramEnrollmentsFilters, run_student_program_enrollments_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.student_program_enrollments")

class StudentProgramEnrollmentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `student_program_enrollments`.
    """

    name = "lc.student_program_enrollments_table"
    intent = "student_program_enrollments"
    intent_aliases = ['student_program_enrollments', 'student program enrollments', 'program enrollments', 'student program enrollment list', 'student program roster', 'program-level student enrollments', 'show student program enrollments', 'list student program enrollments', 'student program participation']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_student_program_enrollments_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(StudentProgramEnrollmentsTableAgent())
