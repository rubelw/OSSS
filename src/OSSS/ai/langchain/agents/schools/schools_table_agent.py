# Auto-generated LangChain agent for QueryData mode="schools"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .schools_table import SchoolsFilters, run_schools_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.schools")

class SchoolsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `schools`.
    """

    name = "lc.schools_table"
    intent = "schools"
    intent_aliases = ['schools', 'school list', 'list schools', 'dcg schools', 'district schools', 'school buildings', 'school directory']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_schools_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(SchoolsTableAgent())
