# Auto-generated LangChain agent for QueryData mode="gl_account_segments"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .gl_account_segments_table import GlAccountSegmentsFilters, run_gl_account_segments_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.gl_account_segments")

class GlAccountSegmentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `gl_account_segments`.
    """

    name = "lc.gl_account_segments_table"
    intent = "gl_account_segments"
    intent_aliases = ['gl account segments', 'gl_account_segments', 'account segment mapping', 'general ledger account segments', 'chart of accounts segments mapping', 'coa account segments']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_gl_account_segments_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(GlAccountSegmentsTableAgent())
