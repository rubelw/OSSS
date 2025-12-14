# Auto-generated LangChain agent for QueryData mode="academic_terms"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .academic_terms_table import AcademicTermsFilters, run_academic_terms_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.academic_terms")

class AcademicTermsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `academic_terms`.
    """

    name = "lc.academic_terms_table"
    intent = "academic_terms"
    intent_aliases = ['academic terms', 'academic_terms', 'semesters and trimesters', 'school terms']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_academic_terms_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(AcademicTermsTableAgent())
