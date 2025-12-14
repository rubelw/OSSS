# Auto-generated LangChain agent for QueryData mode="publications"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .publications_table import PublicationsFilters, run_publications_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.publications")

class PublicationsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `publications`.
    """

    name = "lc.publications_table"
    intent = "publications"
    intent_aliases = ['publications', 'board publications', 'district publications', 'policy publications', 'meeting publications', 'dcg publications', 'osss publications']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_publications_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PublicationsTableAgent())
