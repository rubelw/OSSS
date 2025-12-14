# Auto-generated LangChain agent for QueryData mode="notifications"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .notifications_table import NotificationsFilters, run_notifications_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.notifications")

class NotificationsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `notifications`.
    """

    name = "lc.notifications_table"
    intent = "notifications"
    intent_aliases = ['notifications', 'alerts', 'messages sent', 'parent notifications', 'staff notifications', 'osss notifications']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_notifications_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(NotificationsTableAgent())
