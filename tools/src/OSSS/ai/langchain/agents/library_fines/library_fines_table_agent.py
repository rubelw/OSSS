# Auto-generated LangChain agent for QueryData mode="library_fines"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .library_fines_table import LibraryFinesFilters, run_library_fines_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.library_fines")

class LibraryFinesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `library_fines`.
    """

    name = "lc.library_fines_table"
    intent = "library_fines"
    intent_aliases = ['library fines', 'library_fines', 'overdue fines', 'book fines', 'dcg library fines']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_library_fines_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(LibraryFinesTableAgent())
