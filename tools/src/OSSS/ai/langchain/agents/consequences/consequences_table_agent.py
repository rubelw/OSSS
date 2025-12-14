# Auto-generated LangChain agent for QueryData mode="consequences"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .consequences_table import ConsequencesFilters, run_consequences_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.consequences")

class ConsequencesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `consequences`.
    """

    name = "lc.consequences_table"
    intent = "consequences"
    intent_aliases = ['consequences', 'behavior consequences', 'discipline consequences']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_consequences_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ConsequencesTableAgent())
