# Auto-generated LangChain agent for QueryData mode="journal_batches"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .journal_batches_table import JournalBatchesFilters, run_journal_batches_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.journal_batches")

class JournalBatchesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `journal_batches`.
    """

    name = "lc.journal_batches_table"
    intent = "journal_batches"
    intent_aliases = ['journal_batches', 'journal batches', 'gl batches', 'ledger batches']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_journal_batches_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(JournalBatchesTableAgent())
