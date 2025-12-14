# Auto-generated LangChain agent for QueryData mode="posts"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .posts_table import PostsFilters, run_posts_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.posts")

class PostsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `posts`.
    """

    name = "lc.posts_table"
    intent = "posts"
    intent_aliases = ['posts', 'post list', 'dcg posts', 'osss posts', 'district posts', 'blog posts', 'news posts']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_posts_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PostsTableAgent())
