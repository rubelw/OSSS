# Auto-generated LangChain agent for QueryData mode="incident_participants"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .incident_participants_table import IncidentParticipantsFilters, run_incident_participants_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.incident_participants")

class IncidentParticipantsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `incident_participants`.
    """

    name = "lc.incident_participants_table"
    intent = "incident_participants"
    intent_aliases = ['incident_participants', 'incident participants', 'incident people', 'incident students list']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_incident_participants_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(IncidentParticipantsTableAgent())
