# Auto-generated LangChain agent for QueryData mode="grade_scale_bands"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .grade_scale_bands_table import GradeScaleBandsFilters, run_grade_scale_bands_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.grade_scale_bands")

class GradeScaleBandsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `grade_scale_bands`.
    """

    name = "lc.grade_scale_bands_table"
    intent = "grade_scale_bands"
    intent_aliases = ['grade scale bands', 'grade_scale_bands', 'grading bands', 'grade bands', 'grade bands for scale', 'letter grade bands', 'percentage bands', 'grade breakpoints', 'grade cutoffs by band']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_grade_scale_bands_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(GradeScaleBandsTableAgent())
