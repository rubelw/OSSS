# Auto-generated LangChain agent for QueryData mode="curriculum_versions"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .curriculum_versions_table import CurriculumVersionsFilters, run_curriculum_versions_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.curriculum_versions")

class CurriculumVersionsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `curriculum_versions`.
    """

    name = "lc.curriculum_versions_table"
    intent = "curriculum_versions"
    intent_aliases = ['curriculum versions', 'curriculum_versions', 'curriculum version history', 'versions of curriculum']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_curriculum_versions_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(CurriculumVersionsTableAgent())
