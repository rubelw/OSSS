# Auto-generated LangChain agent for QueryData mode="section_meetings"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .section_meetings_table import SectionMeetingsFilters, run_section_meetings_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.section_meetings")

class SectionMeetingsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `section_meetings`.
    """

    name = "lc.section_meetings_table"
    intent = "section_meetings"
    intent_aliases = ['section meetings', 'section_meetings', 'class meeting times', 'when does this section meet']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_section_meetings_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(SectionMeetingsTableAgent())
