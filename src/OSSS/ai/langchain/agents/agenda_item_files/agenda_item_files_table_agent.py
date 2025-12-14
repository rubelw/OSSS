# Auto-generated LangChain agent for QueryData mode="agenda_item_files"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .agenda_item_files_table import AgendaItemFilesFilters, run_agenda_item_files_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.agenda_item_files")

class AgendaItemFilesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `agenda_item_files`.
    """

    name = "lc.agenda_item_files_table"
    intent = "agenda_item_files"
    intent_aliases = ['agenda item files', 'agenda_item_files', 'attachments for agenda items']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_agenda_item_files_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(AgendaItemFilesTableAgent())
