# Auto-generated LangChain agent for QueryData mode="goals"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .goals_table import GoalsFilters, run_goals_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.goals")

class GoalsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `goals`.
    """

    name = "lc.goals_table"
    intent = "goals"
    intent_aliases = ['goals', 'student goals', 'academic goals', 'behavior goals', 'district goals', 'school improvement goals', 'iep goals']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_goals_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(GoalsTableAgent())
