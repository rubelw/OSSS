# Auto-generated LangChain agent for QueryData mode="folders"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .folders_table import FoldersFilters, run_folders_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.folders")

class FoldersTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `folders`.
    """

    name = "lc.folders_table"
    intent = "folders"
    intent_aliases = ['folders', 'osss folders', 'content folders', 'data folders', 'folder list']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_folders_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(FoldersTableAgent())
