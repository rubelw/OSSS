# Auto-generated LangChain agent for QueryData mode="states"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .states_table import StatesFilters, run_states_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.states")

class StatesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `states`.
    """

    name = "lc.states_table"
    intent = "states"
    intent_aliases = ['states', 'state list', 'list of states', 'us states', 'state codes', 'state abbreviations', 'show states', 'show state list']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_states_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(StatesTableAgent())
