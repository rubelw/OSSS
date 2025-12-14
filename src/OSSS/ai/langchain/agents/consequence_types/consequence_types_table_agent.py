# Auto-generated LangChain agent for QueryData mode="consequence_types"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .consequence_types_table import ConsequenceTypesFilters, run_consequence_types_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.consequence_types")

class ConsequenceTypesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `consequence_types`.
    """

    name = "lc.consequence_types_table"
    intent = "consequence_types"
    intent_aliases = ['consequence types', 'consequence_types', 'discipline consequence types']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_consequence_types_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ConsequenceTypesTableAgent())
