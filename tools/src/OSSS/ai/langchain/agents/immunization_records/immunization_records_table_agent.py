# Auto-generated LangChain agent for QueryData mode="immunization_records"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .immunization_records_table import ImmunizationRecordsFilters, run_immunization_records_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.immunization_records")

class ImmunizationRecordsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `immunization_records`.
    """

    name = "lc.immunization_records_table"
    intent = "immunization_records"
    intent_aliases = ['immunization records', 'immunization_records', 'student immunizations', 'vaccine records']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_immunization_records_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ImmunizationRecordsTableAgent())
