# Auto-generated LangChain agent for QueryData mode="contacts"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .contacts_table import ContactsFilters, run_contacts_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.contacts")

class ContactsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `contacts`.
    """

    name = "lc.contacts_table"
    intent = "contacts"
    intent_aliases = ['contacts', 'contact records', 'parent contacts', 'guardian contacts']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_contacts_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ContactsTableAgent())
