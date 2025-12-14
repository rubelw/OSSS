# Auto-generated LangChain agent for QueryData mode="resolutions"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .resolutions_table import ResolutionsFilters, run_resolutions_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.resolutions")

class ResolutionsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `resolutions`.
    """

    name = "lc.resolutions_table"
    intent = "resolutions"
    intent_aliases = ['resolutions', 'board resolutions', 'policy resolutions', 'meeting resolutions', 'dcg resolutions', 'osss resolutions', 'adopted resolutions', 'approved resolutions', 'resolution records', 'list resolutions', 'show resolutions']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_resolutions_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ResolutionsTableAgent())
