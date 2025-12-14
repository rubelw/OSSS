# Auto-generated LangChain agent for QueryData mode="health_profiles"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .health_profiles_table import HealthProfilesFilters, run_health_profiles_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.health_profiles")

class HealthProfilesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `health_profiles`.
    """

    name = "lc.health_profiles_table"
    intent = "health_profiles"
    intent_aliases = ['health profiles', 'health_profiles', 'student health profiles', 'medical profiles']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_health_profiles_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(HealthProfilesTableAgent())
