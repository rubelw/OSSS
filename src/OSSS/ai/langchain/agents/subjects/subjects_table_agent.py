# Auto-generated LangChain agent for QueryData mode="subjects"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .subjects_table import SubjectsFilters, run_subjects_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.subjects")

class SubjectsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `subjects`.
    """

    name = "lc.subjects_table"
    intent = "subjects"
    intent_aliases = ['subjects', 'course subjects', 'subject list', 'list subjects', 'show subjects', 'all subjects']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_subjects_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(SubjectsTableAgent())
