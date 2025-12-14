# Auto-generated LangChain agent for QueryData mode="pm_plans"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .pm_plans_table import PmPlansFilters, run_pm_plans_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.pm_plans")

class PmPlansTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `pm_plans`.
    """

    name = "lc.pm_plans_table"
    intent = "pm_plans"
    intent_aliases = ['pm plans', 'pm_plans', 'project management plans', 'performance management plans', 'dcg pm plans', 'osss pm plans']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_pm_plans_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PmPlansTableAgent())
