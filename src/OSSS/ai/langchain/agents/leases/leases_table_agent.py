# Auto-generated LangChain agent for QueryData mode="leases"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .leases_table import LeasesFilters, run_leases_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.leases")

class LeasesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `leases`.
    """

    name = "lc.leases_table"
    intent = "leases"
    intent_aliases = ['leases', 'facility leases', 'equipment leases', 'rental agreements', 'dcg leases']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_leases_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(LeasesTableAgent())
