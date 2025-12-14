# Auto-generated LangChain agent for QueryData mode="person_contacts"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .person_contacts_table import PersonContactsFilters, run_person_contacts_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.person_contacts")

class PersonContactsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `person_contacts`.
    """

    name = "lc.person_contacts_table"
    intent = "person_contacts"
    intent_aliases = ['person contacts', 'contact info', 'phone numbers', 'email addresses', 'person_contacts', 'dcg person contacts']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_person_contacts_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PersonContactsTableAgent())
