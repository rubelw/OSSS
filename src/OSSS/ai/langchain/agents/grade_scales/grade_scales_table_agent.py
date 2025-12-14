# Auto-generated LangChain agent for QueryData mode="grade_scales"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .grade_scales_table import GradeScalesFilters, run_grade_scales_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.grade_scales")

class GradeScalesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `grade_scales`.
    """

    name = "lc.grade_scales_table"
    intent = "grade_scales"
    intent_aliases = ['grade scales', 'grade_scales', 'grading scales', 'grading scale', 'letter grade scale', 'numeric grade scale', 'gpa scale', '4.0 scale', 'grading thresholds', 'grade cutoffs']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_grade_scales_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(GradeScalesTableAgent())
