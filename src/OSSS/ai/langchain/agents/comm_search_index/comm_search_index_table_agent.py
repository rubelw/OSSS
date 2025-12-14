# Auto-generated LangChain agent for QueryData mode="comm_search_index"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .comm_search_index_table import CommSearchIndexFilters, run_comm_search_index_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.comm_search_index")

class CommSearchIndexTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `comm_search_index`.
    """

    name = "lc.comm_search_index_table"
    intent = "comm_search_index"
    intent_aliases = ['comm search index', 'comm_search_index', 'communication search index', 'communications index']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_comm_search_index_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(CommSearchIndexTableAgent())
