# Auto-generated LangChain agent for QueryData mode="plan_filters"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .plan_filters_table import PlanFiltersFilters, run_plan_filters_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.plan_filters")

class PlanFiltersTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `plan_filters`.
    """

    name = "lc.plan_filters_table"
    intent = "plan_filters"
    intent_aliases = ['plan filters', 'plan_filters', 'saved plan filters', 'plan filter presets', 'dcg plan filters', 'osss plan filters']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_plan_filters_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PlanFiltersTableAgent())
