# Auto-generated LangChain agent for QueryData mode="files"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .files_table import FilesFilters, run_files_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.files")

class FilesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `files`.
    """

    name = "lc.files_table"
    intent = "files"
    intent_aliases = ['files', 'uploaded files', 'osss files', 'document files', 'attachment files', 'file list']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_files_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(FilesTableAgent())
