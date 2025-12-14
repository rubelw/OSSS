# Auto-generated LangChain agent for QueryData mode="warranties"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .warranties_table import WarrantiesFilters, run_warranties_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.warranties")

class WarrantiesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `warranties`.
    """

    name = "lc.warranties_table"
    intent = "warranties"
    intent_aliases = ['warranties', 'warranty', 'asset warranties', 'equipment warranty']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_warranties_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(WarrantiesTableAgent())
