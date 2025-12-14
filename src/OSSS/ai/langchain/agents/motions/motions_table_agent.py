# Auto-generated LangChain agent for QueryData mode="motions"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .motions_table import MotionsFilters, run_motions_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.motions")

class MotionsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `motions`.
    """

    name = "lc.motions_table"
    intent = "motions"
    intent_aliases = ['motions', 'board motions', 'meeting motions', 'voting motions', 'dcg motions', 'osss motions']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_motions_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MotionsTableAgent())
