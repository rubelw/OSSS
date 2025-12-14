# Auto-generated LangChain agent for QueryData mode="grade_levels"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .grade_levels_table import GradeLevelsFilters, run_grade_levels_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.grade_levels")

class GradeLevelsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `grade_levels`.
    """

    name = "lc.grade_levels_table"
    intent = "grade_levels"
    intent_aliases = ['grade levels', 'grade_levels', 'grades (k-12)', 'elementary grades', 'middle school grades', 'high school grades', 'k-12 grade levels', 'school grade structure', 'grade level list']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_grade_levels_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(GradeLevelsTableAgent())
