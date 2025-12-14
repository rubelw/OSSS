# Auto-generated LangChain agent for QueryData mode="activities"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .activities_table import ActivitiesFilters, run_activities_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.activities")

class ActivitiesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `activities`.
    """

    name = "lc.activities_table"
    intent = "activities"
    intent_aliases = ['activities', 'student activities', 'school activities', 'athletics and activities']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_activities_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ActivitiesTableAgent())
