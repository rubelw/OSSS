# Auto-generated LangChain agent for QueryData mode="section_room_assignments"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .section_room_assignments_table import SectionRoomAssignmentsFilters, run_section_room_assignments_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.section_room_assignments")

class SectionRoomAssignmentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `section_room_assignments`.
    """

    name = "lc.section_room_assignments_table"
    intent = "section_room_assignments"
    intent_aliases = ['section_room_assignments', 'section room assignments', 'room assignments by section', 'which room is this section in', 'classroom assignments', 'section classroom assignments', 'schedule room assignments', 'show section room assignments', 'list section room assignments']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_section_room_assignments_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(SectionRoomAssignmentsTableAgent())
