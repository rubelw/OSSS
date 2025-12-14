# Auto-generated LangChain agent for QueryData mode="emergency_contacts"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .emergency_contacts_table import EmergencyContactsFilters, run_emergency_contacts_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.emergency_contacts")

class EmergencyContactsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `emergency_contacts`.
    """

    name = "lc.emergency_contacts_table"
    intent = "emergency_contacts"
    intent_aliases = ['emergency contacts', 'emergency_contacts', 'student emergency contacts', 'staff emergency contacts', 'contact list for emergencies']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_emergency_contacts_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(EmergencyContactsTableAgent())
