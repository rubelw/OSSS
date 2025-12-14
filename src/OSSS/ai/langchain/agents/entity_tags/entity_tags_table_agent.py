# Auto-generated LangChain agent for QueryData mode="entity_tags"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .entity_tags_table import EntityTagsFilters, run_entity_tags_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.entity_tags")

class EntityTagsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `entity_tags`.
    """

    name = "lc.entity_tags_table"
    intent = "entity_tags"
    intent_aliases = ['entity tags', 'entity_tags', 'tags on folders', 'tags on files', 'osss tags']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_entity_tags_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(EntityTagsTableAgent())
