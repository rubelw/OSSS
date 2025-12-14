# Auto-generated LangChain agent for QueryData mode="spaces"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .spaces_table import SpacesFilters, run_spaces_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.spaces")

class SpacesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `spaces`.
    """

    name = "lc.spaces_table"
    intent = "spaces"
    intent_aliases = ['spaces', 'space list', 'facility spaces', 'rooms and spaces', 'available spaces', 'list spaces', 'show spaces']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_spaces_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(SpacesTableAgent())
