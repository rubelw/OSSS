# Auto-generated LangChain agent for QueryData mode="fees"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .fees_table import FeesFilters, run_fees_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.fees")

class FeesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `fees`.
    """

    name = "lc.fees_table"
    intent = "fees"
    intent_aliases = ['fees', 'student fees', 'school fees', 'activity fees', 'course fees', 'fee list']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_fees_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(FeesTableAgent())
