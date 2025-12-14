# Auto-generated LangChain agent for QueryData mode="waivers"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .waivers_table import WaiversFilters, run_waivers_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.waivers")

class WaiversTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `waivers`.
    """

    name = "lc.waivers_table"
    intent = "waivers"
    intent_aliases = ['waivers', 'waiver', 'student waivers', 'program waivers', 'fee waivers']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_waivers_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(WaiversTableAgent())
