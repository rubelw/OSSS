# Auto-generated LangChain agent for QueryData mode="scan_requests"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .scan_requests_table import ScanRequestsFilters, run_scan_requests_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.scan_requests")

class ScanRequestsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `scan_requests`.
    """

    name = "lc.scan_requests_table"
    intent = "scan_requests"
    intent_aliases = ['scan_requests', 'scan requests', 'scan queue', 'queued scans', 'requested scans', 'pending scans', 'scheduled scans']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_scan_requests_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ScanRequestsTableAgent())
