# Auto-generated LangChain agent for QueryData mode="iep_plans"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .iep_plans_table import IepPlansFilters, run_iep_plans_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.iep_plans")

class IepPlansTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `iep_plans`.
    """

    name = "lc.iep_plans_table"
    intent = "iep_plans"
    intent_aliases = ['iep plans', 'iep_plans', 'IEP list', 'student IEPs', 'special education plans']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_iep_plans_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(IepPlansTableAgent())
