# Auto-generated LangChain agent for QueryData mode="education_associations"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .education_associations_table import EducationAssociationsFilters, run_education_associations_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.education_associations")

class EducationAssociationsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `education_associations`.
    """

    name = "lc.education_associations_table"
    intent = "education_associations"
    intent_aliases = ['education associations', 'education_associations', 'school associations', 'district associations', 'academic associations']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_education_associations_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(EducationAssociationsTableAgent())
