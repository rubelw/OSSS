# Auto-generated LangChain agent for QueryData mode="export_runs"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .export_runs_table import ExportRunsFilters, run_export_runs_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.export_runs")

class ExportRunsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `export_runs`.
    """

    name = "lc.export_runs_table"
    intent = "export_runs"
    intent_aliases = ['export_runs', 'export runs', 'data export runs', 'export history', 'csv export runs', 'job export runs']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_export_runs_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ExportRunsTableAgent())
