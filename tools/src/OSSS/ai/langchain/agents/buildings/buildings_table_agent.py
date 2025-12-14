# Auto-generated LangChain agent for QueryData mode="buildings"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .buildings_table import BuildingsFilters, run_buildings_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.buildings")

class BuildingsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `buildings`.
    """

    name = "lc.buildings_table"
    intent = "buildings"
    intent_aliases = ['buildings', 'school buildings', 'district buildings']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_buildings_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(BuildingsTableAgent())
