# Auto-generated LangChain agent for QueryData mode="agenda_item_approvals"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .agenda_item_approvals_table import AgendaItemApprovalsFilters, run_agenda_item_approvals_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.agenda_item_approvals")

class AgendaItemApprovalsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `agenda_item_approvals`.
    """

    name = "lc.agenda_item_approvals_table"
    intent = "agenda_item_approvals"
    intent_aliases = ['agenda item approvals', 'agenda_item_approvals', 'approvals for agenda items']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_agenda_item_approvals_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(AgendaItemApprovalsTableAgent())
