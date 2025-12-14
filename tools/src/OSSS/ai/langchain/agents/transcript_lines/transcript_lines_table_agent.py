# Auto-generated LangChain agent for QueryData mode="transcript_lines"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .transcript_lines_table import TranscriptLinesFilters, run_transcript_lines_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.transcript_lines")

class TranscriptLinesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `transcript_lines`.
    """

    name = "lc.transcript_lines_table"
    intent = "transcript_lines"
    intent_aliases = ['transcript_lines', 'transcript lines']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_transcript_lines_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(TranscriptLinesTableAgent())
