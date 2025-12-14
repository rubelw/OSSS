# Auto-generated LangChain agent for QueryData mode="scan_results"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .scan_results_table import ScanResultsFilters, run_scan_results_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.scan_results")

class ScanResultsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `scan_results`.
    """

    name = "lc.scan_results_table"
    intent = "scan_results"
    intent_aliases = ['scan_results', 'scan results', 'security scans', 'scan findings', 'scan output', 'scanner results']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_scan_results_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ScanResultsTableAgent())
