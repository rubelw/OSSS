# Auto-generated LangChain agent for QueryData mode="gl_segments"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .gl_segments_table import GlSegmentsFilters, run_gl_segments_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.gl_segments")

class GlSegmentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `gl_segments`.
    """

    name = "lc.gl_segments_table"
    intent = "gl_segments"
    intent_aliases = ['gl segments', 'gl_segments', 'general ledger segments', 'chart of accounts segments', 'accounting segments', 'fund segments', 'function segments', 'project segments']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_gl_segments_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(GlSegmentsTableAgent())
