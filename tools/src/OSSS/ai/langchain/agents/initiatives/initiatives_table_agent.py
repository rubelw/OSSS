# Auto-generated LangChain agent for QueryData mode="initiatives"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .initiatives_table import InitiativesFilters, run_initiatives_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.initiatives")

class InitiativesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `initiatives`.
    """

    name = "lc.initiatives_table"
    intent = "initiatives"
    intent_aliases = ['initiatives', 'strategic initiatives', 'district initiatives', 'osss initiatives', 'improvement initiatives']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_initiatives_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(InitiativesTableAgent())
