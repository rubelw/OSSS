# Auto-generated LangChain agent for QueryData mode="meeting_permissions"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .meeting_permissions_table import MeetingPermissionsFilters, run_meeting_permissions_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.meeting_permissions")

class MeetingPermissionsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `meeting_permissions`.
    """

    name = "lc.meeting_permissions_table"
    intent = "meeting_permissions"
    intent_aliases = ['meeting permissions', 'meeting_permissions', 'who can see meetings', 'meeting access control']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_meeting_permissions_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MeetingPermissionsTableAgent())
