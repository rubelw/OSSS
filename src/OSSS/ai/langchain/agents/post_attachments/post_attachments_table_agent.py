# Auto-generated LangChain agent for QueryData mode="post_attachments"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .post_attachments_table import PostAttachmentsFilters, run_post_attachments_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.post_attachments")

class PostAttachmentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `post_attachments`.
    """

    name = "lc.post_attachments_table"
    intent = "post_attachments"
    intent_aliases = ['post attachments', 'attachments for posts', 'dcg post attachments', 'osss post attachments', 'attached documents', 'attached files', 'files attached to posts']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_post_attachments_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PostAttachmentsTableAgent())
