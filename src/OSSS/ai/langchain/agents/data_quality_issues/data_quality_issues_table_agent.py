# Auto-generated LangChain agent for QueryData mode="data_quality_issues"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .data_quality_issues_table import DataQualityIssuesFilters, run_data_quality_issues_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.data_quality_issues")

class DataQualityIssuesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `data_quality_issues`.
    """

    name = "lc.data_quality_issues_table"
    intent = "data_quality_issues"
    intent_aliases = ['data quality issues', 'data_quality_issues', 'dq issues', 'data validation issues', 'data quality problems']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_data_quality_issues_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(DataQualityIssuesTableAgent())
