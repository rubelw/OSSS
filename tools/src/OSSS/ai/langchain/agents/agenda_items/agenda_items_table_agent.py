# Auto-generated LangChain agent for QueryData mode="agenda_items"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .agenda_items_table import AgendaItemsFilters, run_agenda_items_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.agenda_items")

class AgendaItemsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `agenda_items`.
    """

    name = "lc.agenda_items_table"
    intent = "agenda_items"
    intent_aliases = ['agenda items', 'agenda_items', 'board agenda items']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_agenda_items_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(AgendaItemsTableAgent())
