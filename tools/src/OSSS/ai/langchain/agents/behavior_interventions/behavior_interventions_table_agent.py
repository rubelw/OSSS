# Auto-generated LangChain agent for QueryData mode="behavior_interventions"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .behavior_interventions_table import BehaviorInterventionsFilters, run_behavior_interventions_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.behavior_interventions")

class BehaviorInterventionsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `behavior_interventions`.
    """

    name = "lc.behavior_interventions_table"
    intent = "behavior_interventions"
    intent_aliases = ['behavior interventions', 'behavior_interventions', 'behavior supports', 'mtss interventions']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_behavior_interventions_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(BehaviorInterventionsTableAgent())
