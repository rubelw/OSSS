# Auto-generated LangChain agent for QueryData mode="frameworks"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .frameworks_table import FrameworksFilters, run_frameworks_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.frameworks")

class FrameworksTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `frameworks`.
    """

    name = "lc.frameworks_table"
    intent = "frameworks"
    intent_aliases = ['frameworks', 'academic frameworks', 'curriculum frameworks', 'standards frameworks', 'instructional frameworks']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_frameworks_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(FrameworksTableAgent())
