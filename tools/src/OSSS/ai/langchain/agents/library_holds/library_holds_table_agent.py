# Auto-generated LangChain agent for QueryData mode="library_holds"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .library_holds_table import LibraryHoldsFilters, run_library_holds_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.library_holds")

class LibraryHoldsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `library_holds`.
    """

    name = "lc.library_holds_table"
    intent = "library_holds"
    intent_aliases = ['library holds', 'library_holds', 'book holds', 'holds on books', 'dcg library holds']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_library_holds_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(LibraryHoldsTableAgent())
