# Auto-generated LangChain agent for QueryData mode="governing_bodies"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .governing_bodies_table import GoverningBodiesFilters, run_governing_bodies_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.governing_bodies")

class GoverningBodiesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `governing_bodies`.
    """

    name = "lc.governing_bodies_table"
    intent = "governing_bodies"
    intent_aliases = ['governing bodies', 'governing_bodies', 'school board', 'board of education', 'district governing body', 'governance body', 'oversight body']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_governing_bodies_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(GoverningBodiesTableAgent())
