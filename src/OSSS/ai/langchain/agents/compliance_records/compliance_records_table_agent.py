# Auto-generated LangChain agent for QueryData mode="compliance_records"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .compliance_records_table import ComplianceRecordsFilters, run_compliance_records_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.compliance_records")

class ComplianceRecordsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `compliance_records`.
    """

    name = "lc.compliance_records_table"
    intent = "compliance_records"
    intent_aliases = ['compliance records', 'compliance_records', 'training compliance', 'background check compliance']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_compliance_records_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ComplianceRecordsTableAgent())
