# Auto-generated LangChain agent for QueryData mode="immunizations"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .immunizations_table import ImmunizationsFilters, run_immunizations_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.immunizations")

class ImmunizationsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `immunizations`.
    """

    name = "lc.immunizations_table"
    intent = "immunizations"
    intent_aliases = ['immunizations', 'immunization types', 'vaccine types', 'required immunizations']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_immunizations_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ImmunizationsTableAgent())
