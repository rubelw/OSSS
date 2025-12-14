# Auto-generated LangChain agent for QueryData mode="library_checkouts"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .library_checkouts_table import LibraryCheckoutsFilters, run_library_checkouts_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.library_checkouts")

class LibraryCheckoutsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `library_checkouts`.
    """

    name = "lc.library_checkouts_table"
    intent = "library_checkouts"
    intent_aliases = ['library checkouts', 'library_checkouts', 'checked out books', 'books checked out', 'dcg library checkouts']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_library_checkouts_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(LibraryCheckoutsTableAgent())
