# Auto-generated LangChain agent for QueryData mode="embeds"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .embeds_table import EmbedsFilters, run_embeds_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.embeds")

class EmbedsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `embeds`.
    """

    name = "lc.embeds_table"
    intent = "embeds"
    intent_aliases = ['embeds', 'embeddings', 'vector index', 'rag index entries', 'osss embeddings']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_embeds_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(EmbedsTableAgent())
