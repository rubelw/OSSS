# Auto-generated LangChain agent for QueryData mode="asset_parts"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .asset_parts_table import AssetPartsFilters, run_asset_parts_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.asset_parts")

class AssetPartsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `asset_parts`.
    """

    name = "lc.asset_parts_table"
    intent = "asset_parts"
    intent_aliases = ['asset parts', 'asset_parts', 'spare parts', 'replacement parts']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_asset_parts_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(AssetPartsTableAgent())
