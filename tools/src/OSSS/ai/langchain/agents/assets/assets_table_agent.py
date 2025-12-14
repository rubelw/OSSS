# Auto-generated LangChain agent for QueryData mode="assets"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .assets_table import AssetsFilters, run_assets_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.assets")

class AssetsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `assets`.
    """

    name = "lc.assets_table"
    intent = "assets"
    intent_aliases = ['assets', 'fixed assets', 'inventory assets', 'equipment inventory']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_assets_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(AssetsTableAgent())
