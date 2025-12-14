# Auto-generated LangChain agent for QueryData mode="persons"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .persons_table import PersonsFilters, run_persons_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.persons")

class PersonsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `persons`.
    """

    name = "lc.persons_table"
    intent = "persons"
    intent_aliases = ['persons', 'people', 'person records', 'person list', 'dcg persons', 'osss persons']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_persons_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PersonsTableAgent())
