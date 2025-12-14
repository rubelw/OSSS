# Auto-generated LangChain agent for QueryData mode="plans"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .plans_table import PlansFilters, run_plans_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.plans")

class PlansTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `plans`.
    """

    name = "lc.plans_table"
    intent = "plans"
    intent_aliases = ['plans', 'plan list', 'district plans', 'strategic plans', 'dcg plans', 'osss plans']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_plans_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PlansTableAgent())
