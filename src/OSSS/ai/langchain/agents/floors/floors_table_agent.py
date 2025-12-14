# Auto-generated LangChain agent for QueryData mode="floors"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .floors_table import FloorsFilters, run_floors_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.floors")

class FloorsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `floors`.
    """

    name = "lc.floors_table"
    intent = "floors"
    intent_aliases = ['floors', 'building floors', 'school floors', 'campus floors', 'floor list']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_floors_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(FloorsTableAgent())
