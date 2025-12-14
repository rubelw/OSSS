# Auto-generated LangChain agent for QueryData mode="curricula"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .curricula_table import CurriculaFilters, run_curricula_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.curricula")

class CurriculaTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `curricula`.
    """

    name = "lc.curricula_table"
    intent = "curricula"
    intent_aliases = ['curricula', 'curriculum list', 'curriculum catalog', 'instructional programs']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_curricula_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(CurriculaTableAgent())
