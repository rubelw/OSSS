# Auto-generated LangChain agent for QueryData mode="plan_alignments"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .plan_alignments_table import PlanAlignmentsFilters, run_plan_alignments_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.plan_alignments")

class PlanAlignmentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `plan_alignments`.
    """

    name = "lc.plan_alignments_table"
    intent = "plan_alignments"
    intent_aliases = ['plan alignments', 'plan_alignments', 'alignment between plans', 'plans aligned to', 'dcg plan alignments', 'osss plan alignments']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_plan_alignments_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(PlanAlignmentsTableAgent())
