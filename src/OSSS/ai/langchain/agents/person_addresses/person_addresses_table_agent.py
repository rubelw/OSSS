# Auto-generated LangChain agent for QueryData mode="person_addresses"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .person_addresses_table import PersonAddressesFilters, run_person_addresses_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.person_addresses")

class PersonAddressesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `person_addresses`.
    """

    name = "lc.person_addresses_table"
    intent = "person_addresses"
    intent_aliases = ['person addresses', 'home address', 'mailing address', 'person_addresses', 'dcg person addresses']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_person_addresses_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PersonAddressesTableAgent())
