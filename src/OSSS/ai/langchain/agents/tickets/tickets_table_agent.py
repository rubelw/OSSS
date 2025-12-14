# Auto-generated LangChain agent for QueryData mode="tickets"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .tickets_table import TicketsFilters, run_tickets_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.tickets")

class TicketsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `tickets`.
    """

    name = "lc.tickets_table"
    intent = "tickets"
    intent_aliases = ['tickets', 'ticket list', 'ticket inventory', 'ticket sales', 'event tickets', 'show tickets', 'tickets report']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_tickets_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(TicketsTableAgent())
