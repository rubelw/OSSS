# Auto-generated LangChain agent for QueryData mode="ticket_scans"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .ticket_scans_table import TicketScansFilters, run_ticket_scans_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.ticket_scans")

class TicketScansTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `ticket_scans`.
    """

    name = "lc.ticket_scans_table"
    intent = "ticket_scans"
    intent_aliases = ['ticket_scans', 'ticket scans', 'scan logs', 'ticket scan logs', 'ticket check-ins', 'ticket checkins', 'gate scans', 'entry scans']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_ticket_scans_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(TicketScansTableAgent())
