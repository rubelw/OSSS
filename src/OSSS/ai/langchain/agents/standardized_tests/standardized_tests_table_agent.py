# Auto-generated LangChain agent for QueryData mode="standardized_tests"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .standardized_tests_table import StandardizedTestsFilters, run_standardized_tests_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.standardized_tests")

class StandardizedTestsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `standardized_tests`.
    """

    name = "lc.standardized_tests_table"
    intent = "standardized_tests"
    intent_aliases = ['standardized_tests', 'standardized tests', 'ACT test', 'SAT test', 'Iowa Assessments', 'MAP testing', 'FAST assessment']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_standardized_tests_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(StandardizedTestsTableAgent())
