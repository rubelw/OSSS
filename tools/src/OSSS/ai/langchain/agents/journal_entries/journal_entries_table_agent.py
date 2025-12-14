# Auto-generated LangChain agent for QueryData mode="journal_entries"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .journal_entries_table import JournalEntriesFilters, run_journal_entries_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.journal_entries")

class JournalEntriesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `journal_entries`.
    """

    name = "lc.journal_entries_table"
    intent = "journal_entries"
    intent_aliases = ['journal_entries', 'journal entries', 'gl entries', 'general ledger entries']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_journal_entries_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(JournalEntriesTableAgent())
