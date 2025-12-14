# Auto-generated LangChain agent for QueryData mode="special_education_cases"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .special_education_cases_table import SpecialEducationCasesFilters, run_special_education_cases_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.special_education_cases")

class SpecialEducationCasesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `special_education_cases`.
    """

    name = "lc.special_education_cases_table"
    intent = "special_education_cases"
    intent_aliases = ['special_education_cases', 'special education cases', 'special ed cases', 'special education caseload', 'IEP cases', 'special ed students']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_special_education_cases_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(SpecialEducationCasesTableAgent())
