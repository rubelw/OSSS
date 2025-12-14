# Auto-generated LangChain agent for QueryData mode="pm_work_generators"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .pm_work_generators_table import PmWorkGeneratorsFilters, run_pm_work_generators_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.pm_work_generators")

class PmWorkGeneratorsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `pm_work_generators`.
    """

    name = "lc.pm_work_generators_table"
    intent = "pm_work_generators"
    intent_aliases = ['pm work generators', 'pm_work_generators', 'plan work generators', 'work generation templates', 'dcg pm work generators', 'osss pm work generators']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_pm_work_generators_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PmWorkGeneratorsTableAgent())
