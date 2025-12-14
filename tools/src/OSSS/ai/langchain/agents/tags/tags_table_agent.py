# Auto-generated LangChain agent for QueryData mode="tags"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .tags_table import TagsFilters, run_tags_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.tags")

class TagsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `tags`.
    """

    name = "lc.tags_table"
    intent = "tags"
    intent_aliases = ['tags', 'list tags', 'tag list', 'show tags', 'all tags']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_tags_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(TagsTableAgent())
