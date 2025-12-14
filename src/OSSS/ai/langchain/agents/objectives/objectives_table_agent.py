# Auto-generated LangChain agent for QueryData mode="objectives"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .objectives_table import ObjectivesFilters, run_objectives_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.objectives")

class ObjectivesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `objectives`.
    """

    name = "lc.objectives_table"
    intent = "objectives"
    intent_aliases = ['objectives', 'goals', 'strategic objectives', 'improvement objectives', 'district goals', 'osss objectives']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_objectives_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ObjectivesTableAgent())
