# Auto-generated LangChain agent for QueryData mode="space_reservations"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .space_reservations_table import SpaceReservationsFilters, run_space_reservations_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.space_reservations")

class SpaceReservationsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `space_reservations`.
    """

    name = "lc.space_reservations_table"
    intent = "space_reservations"
    intent_aliases = ['space_reservations', 'space reservations', 'facility reservations', 'room reservations', 'gym reservations', 'auditorium reservations']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_space_reservations_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(SpaceReservationsTableAgent())
