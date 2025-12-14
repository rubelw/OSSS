# Auto-generated LangChain agent for QueryData mode="journal_entry_lines"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .journal_entry_lines_table import JournalEntryLinesFilters, run_journal_entry_lines_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.journal_entry_lines")

class JournalEntryLinesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `journal_entry_lines`.
    """

    name = "lc.journal_entry_lines_table"
    intent = "journal_entry_lines"
    intent_aliases = ['journal_entry_lines', 'journal entry lines', 'gl lines', 'ledger lines']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_journal_entry_lines_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(JournalEntryLinesTableAgent())
