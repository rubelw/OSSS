# Auto-generated LangChain agent for QueryData mode="teacher_section_assignments"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .teacher_section_assignments_table import TeacherSectionAssignmentsFilters, run_teacher_section_assignments_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.teacher_section_assignments")

class TeacherSectionAssignmentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `teacher_section_assignments`.
    """

    name = "lc.teacher_section_assignments_table"
    intent = "teacher_section_assignments"
    intent_aliases = ['teacher_section_assignments', 'teacher section assignments', 'teacher-section assignments', 'teacher assignment sections', 'teacher assignments by section']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_teacher_section_assignments_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(TeacherSectionAssignmentsTableAgent())
