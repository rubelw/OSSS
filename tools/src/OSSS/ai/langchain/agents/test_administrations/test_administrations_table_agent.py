# Auto-generated LangChain agent for QueryData mode="test_administrations"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .test_administrations_table import TestAdministrationsFilters, run_test_administrations_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.test_administrations")

class TestAdministrationsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `test_administrations`.
    """

    name = "lc.test_administrations_table"
    intent = "test_administrations"
    intent_aliases = ['test_administrations', 'test administrations']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_test_administrations_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(TestAdministrationsTableAgent())
