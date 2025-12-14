# Auto-generated LangChain agent for QueryData mode="kpi_datapoints"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .kpi_datapoints_table import KpiDatapointsFilters, run_kpi_datapoints_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.kpi_datapoints")

class KpiDatapointsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `kpi_datapoints`.
    """

    name = "lc.kpi_datapoints_table"
    intent = "kpi_datapoints"
    intent_aliases = ['kpi_datapoints', 'kpi datapoints', 'kpi values', 'kpi history', 'kpi trend']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_kpi_datapoints_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(KpiDatapointsTableAgent())
