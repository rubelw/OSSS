# Auto-generated LangChain agent for QueryData mode="test_results"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .test_results_table import TestResultsFilters, run_test_results_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.test_results")

class TestResultsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `test_results`.
    """

    name = "lc.test_results_table"
    intent = "test_results"
    intent_aliases = ['test_results', 'test results']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_test_results_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(TestResultsTableAgent())
