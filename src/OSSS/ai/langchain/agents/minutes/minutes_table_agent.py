# Auto-generated LangChain agent for QueryData mode="minutes"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .minutes_table import MinutesFilters, run_minutes_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.minutes")

class MinutesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `minutes`.
    """

    name = "lc.minutes_table"
    intent = "minutes"
    intent_aliases = ['minutes', 'meeting minutes', 'board minutes', 'dcg minutes', 'osss minutes']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_minutes_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MinutesTableAgent())
