# Auto-generated LangChain agent for QueryData mode="student_guardians"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .student_guardians_table import StudentGuardiansFilters, run_student_guardians_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.student_guardians")

class StudentGuardiansTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `student_guardians`.
    """

    name = "lc.student_guardians_table"
    intent = "student_guardians"
    intent_aliases = ['student_guardians', 'student guardians', 'guardians', 'emergency contacts', 'parent contacts', 'guardian info', 'guardian information', 'student guardian list', 'list student guardians', 'show student guardians']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_student_guardians_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(StudentGuardiansTableAgent())
