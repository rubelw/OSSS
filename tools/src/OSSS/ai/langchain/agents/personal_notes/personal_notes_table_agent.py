# Auto-generated LangChain agent for QueryData mode="personal_notes"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .personal_notes_table import PersonalNotesFilters, run_personal_notes_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.personal_notes")

class PersonalNotesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `personal_notes`.
    """

    name = "lc.personal_notes_table"
    intent = "personal_notes"
    intent_aliases = ['personal notes', 'notes about person', 'student notes', 'staff notes', 'personal_notes', 'dcg personal notes']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_personal_notes_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PersonalNotesTableAgent())
