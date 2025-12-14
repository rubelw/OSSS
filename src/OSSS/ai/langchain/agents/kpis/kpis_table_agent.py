# Auto-generated LangChain agent for QueryData mode="kpis"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .kpis_table import KpisFilters, run_kpis_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.kpis")

class KpisTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `kpis`.
    """

    name = "lc.kpis_table"
    intent = "kpis"
    intent_aliases = ['kpis', 'kpi dashboard', 'key performance indicators', 'performance metrics', 'district kpis']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_kpis_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(KpisTableAgent())
