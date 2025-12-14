# Auto-generated LangChain agent for QueryData mode="ticket_types"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .ticket_types_table import TicketTypesFilters, run_ticket_types_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.ticket_types")

class TicketTypesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `ticket_types`.
    """

    name = "lc.ticket_types_table"
    intent = "ticket_types"
    intent_aliases = ['ticket_types', 'ticket types', 'helpdesk ticket types', 'support ticket types', 'it ticket types', 'work order ticket types']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_ticket_types_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(TicketTypesTableAgent())
