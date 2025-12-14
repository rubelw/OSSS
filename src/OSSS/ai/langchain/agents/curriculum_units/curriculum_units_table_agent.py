# Auto-generated LangChain agent for QueryData mode="curriculum_units"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .curriculum_units_table import CurriculumUnitsFilters, run_curriculum_units_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.curriculum_units")

class CurriculumUnitsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `curriculum_units`.
    """

    name = "lc.curriculum_units_table"
    intent = "curriculum_units"
    intent_aliases = ['curriculum units', 'curriculum_units', 'units in curriculum', 'scope and sequence units']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_curriculum_units_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(CurriculumUnitsTableAgent())
