# Auto-generated LangChain agent for QueryData mode="plan_search_index"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .plan_search_index_table import PlanSearchIndexFilters, run_plan_search_index_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.plan_search_index")

class PlanSearchIndexTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `plan_search_index`.
    """

    name = "lc.plan_search_index_table"
    intent = "plan_search_index"
    intent_aliases = ['plan search index', 'plan_search_index', 'searchable plans', 'plan search metadata', 'dcg plan search index', 'osss plan search index']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_plan_search_index_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PlanSearchIndexTableAgent())
