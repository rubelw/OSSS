# Auto-generated LangChain agent for QueryData mode="fan_pages"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .fan_pages_table import FanPagesFilters, run_fan_pages_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.fan_pages")

class FanPagesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `fan_pages`.
    """

    name = "lc.fan_pages_table"
    intent = "fan_pages"
    intent_aliases = ['fan_pages', 'fan pages', 'fan page', 'school fan page', 'athletics fan page', 'game day fan page']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_fan_pages_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(FanPagesTableAgent())
