# Auto-generated LangChain agent for QueryData mode="final_grades"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .final_grades_table import FinalGradesFilters, run_final_grades_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.final_grades")

class FinalGradesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `final_grades`.
    """

    name = "lc.final_grades_table"
    intent = "final_grades"
    intent_aliases = ['final grades', 'final_grades', 'final marks', 'report card grades', 'end of term grades', 'posted grades']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_final_grades_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(FinalGradesTableAgent())
