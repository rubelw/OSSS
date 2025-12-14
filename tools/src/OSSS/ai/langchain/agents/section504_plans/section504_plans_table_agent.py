# Auto-generated LangChain agent for QueryData mode="section504_plans"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .section504_plans_table import Section504PlansFilters, run_section504_plans_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.section504_plans")

class Section504PlansTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `section504_plans`.
    """

    name = "lc.section504_plans_table"
    intent = "section504_plans"
    intent_aliases = ['section504_plans', 'section504 plans', '504 plans', 'section 504 plans', 'student 504 plan']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_section504_plans_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(Section504PlansTableAgent())
