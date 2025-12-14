# Auto-generated LangChain agent for QueryData mode="gl_segment_values"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .gl_segment_values_table import GlSegmentValuesFilters, run_gl_segment_values_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.gl_segment_values")

class GlSegmentValuesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `gl_segment_values`.
    """

    name = "lc.gl_segment_values_table"
    intent = "gl_segment_values"
    intent_aliases = ['gl segment values', 'gl_segment_values', 'general ledger segment values', 'accounting segment values', 'chart of accounts values', 'segment value list', 'coas segment values']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_gl_segment_values_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(GlSegmentValuesTableAgent())
