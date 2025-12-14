# Auto-generated LangChain agent for QueryData mode="library_items"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .library_items_table import LibraryItemsFilters, run_library_items_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.library_items")

class LibraryItemsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `library_items`.
    """

    name = "lc.library_items_table"
    intent = "library_items"
    intent_aliases = ['library items', 'library catalog', 'library books', 'library_titles', 'dcg library items', 'osss library items']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_library_items_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(LibraryItemsTableAgent())
