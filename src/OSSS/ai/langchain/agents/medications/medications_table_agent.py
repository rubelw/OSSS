# Auto-generated LangChain agent for QueryData mode="medications"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .medications_table import MedicationsFilters, run_medications_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.medications")

class MedicationsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `medications`.
    """

    name = "lc.medications_table"
    intent = "medications"
    intent_aliases = ['medications', 'medication list', 'nurse medications', 'student medications', 'dcg medications']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_medications_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MedicationsTableAgent())
