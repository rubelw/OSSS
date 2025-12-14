# Auto-generated LangChain agent for QueryData mode="medication_administrations"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .medication_administrations_table import MedicationAdministrationsFilters, run_medication_administrations_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.medication_administrations")

class MedicationAdministrationsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `medication_administrations`.
    """

    name = "lc.medication_administrations_table"
    intent = "medication_administrations"
    intent_aliases = ['medication administrations', 'medication_administrations', 'med admin', 'nurse medication administrations', 'student medication administrations']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_medication_administrations_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(MedicationAdministrationsTableAgent())
