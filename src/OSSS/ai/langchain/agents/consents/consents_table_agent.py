# Auto-generated LangChain agent for QueryData mode="consents"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .consents_table import ConsentsFilters, run_consents_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.consents")

class ConsentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `consents`.
    """

    name = "lc.consents_table"
    intent = "consents"
    intent_aliases = ['consents', 'parent consents', 'guardian consents', 'data usage consents']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_consents_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ConsentsTableAgent())
