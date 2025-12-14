# Auto-generated LangChain agent for QueryData mode="student_transportation_assignments"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .student_transportation_assignments_table import StudentTransportationAssignmentsFilters, run_student_transportation_assignments_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.student_transportation_assignments")

class StudentTransportationAssignmentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `student_transportation_assignments`.
    """

    name = "lc.student_transportation_assignments_table"
    intent = "student_transportation_assignments"
    intent_aliases = ['student_transportation_assignments', 'student transportation assignments', 'transportation assignments', 'bus assignments', 'student bus assignments', 'show transportation assignments', 'list student transportation']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_student_transportation_assignments_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(StudentTransportationAssignmentsTableAgent())
