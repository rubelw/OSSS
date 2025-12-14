# Auto-generated LangChain agent for QueryData mode="requirements"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .requirements_table import RequirementsFilters, run_requirements_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.requirements")

class RequirementsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `requirements`.
    """

    name = "lc.requirements_table"
    intent = "requirements"
    intent_aliases = ['requirements', 'requirement records', 'list requirements', 'show requirements', 'program requirements', 'graduation requirements', 'course requirements', 'eligibility requirements', 'policy requirements', 'dcg requirements', 'osss requirements']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_requirements_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(RequirementsTableAgent())
