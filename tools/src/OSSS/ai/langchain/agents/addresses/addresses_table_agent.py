# Auto-generated LangChain agent for QueryData mode="addresses"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .addresses_table import AddressesFilters, run_addresses_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.addresses")

class AddressesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `addresses`.
    """

    name = "lc.addresses_table"
    intent = "addresses"
    intent_aliases = ['addresses', 'home addresses', 'mailing addresses']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_addresses_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(AddressesTableAgent())
