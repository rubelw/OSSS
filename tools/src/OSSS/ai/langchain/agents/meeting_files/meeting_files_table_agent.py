# Auto-generated LangChain agent for QueryData mode="meeting_files"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .meeting_files_table import MeetingFilesFilters, run_meeting_files_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.meeting_files")

class MeetingFilesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `meeting_files`.
    """

    name = "lc.meeting_files_table"
    intent = "meeting_files"
    intent_aliases = ['meeting files', 'meeting_files', 'files attached to meetings', 'board meeting files']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_meeting_files_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MeetingFilesTableAgent())
