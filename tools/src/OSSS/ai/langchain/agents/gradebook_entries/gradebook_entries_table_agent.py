# Auto-generated LangChain agent for QueryData mode="gradebook_entries"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .gradebook_entries_table import GradebookEntriesFilters, run_gradebook_entries_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.gradebook_entries")

class GradebookEntriesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `gradebook_entries`.
    """

    name = "lc.gradebook_entries_table"
    intent = "gradebook_entries"
    intent_aliases = ['gradebook entries', 'gradebook_entries', 'gradebook', 'student grades', 'student scores', 'assignment grades', 'assignment scores', 'test scores', 'quiz scores', 'exam scores', 'points earned', 'points possible', 'grade details']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_gradebook_entries_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(GradebookEntriesTableAgent())
