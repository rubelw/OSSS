# Auto-generated LangChain agent for QueryData mode="alignments"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .alignments_table import AlignmentsFilters, run_alignments_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.alignments")

class AlignmentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `alignments`.
    """

    name = "lc.alignments_table"
    intent = "alignments"
    intent_aliases = ['alignments', 'standard alignments', 'curriculum alignments']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_alignments_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(AlignmentsTableAgent())
