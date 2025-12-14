# Auto-generated LangChain agent for QueryData mode="nurse_visits"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .nurse_visits_table import NurseVisitsFilters, run_nurse_visits_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.nurse_visits")

class NurseVisitsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `nurse_visits`.
    """

    name = "lc.nurse_visits_table"
    intent = "nurse_visits"
    intent_aliases = ['nurse visits', 'nurse_visits', 'nurse office visits', 'health office visits', 'student nurse visits', 'dcg nurse visits']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_nurse_visits_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(NurseVisitsTableAgent())
