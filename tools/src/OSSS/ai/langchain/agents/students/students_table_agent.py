# Auto-generated LangChain agent for QueryData mode="students"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .students_table import StudentsFilters, run_students_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.students")

class StudentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `students`.
    """

    name = "lc.students_table"
    intent = "students"
    intent_aliases = ['student', 'students', 'roster', 'enrollment', 'class list']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_students_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(StudentsTableAgent())
