# Auto-generated LangChain agent for QueryData mode="scorecard_kpis"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .scorecard_kpis_table import ScorecardKpisFilters, run_scorecard_kpis_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.scorecard_kpis")

class ScorecardKpisTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `scorecard_kpis`.
    """

    name = "lc.scorecard_kpis_table"
    intent = "scorecard_kpis"
    intent_aliases = ['scorecard_kpis', 'scorecard kpis', 'kpis on scorecards', 'plan kpis', 'performance indicators']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_scorecard_kpis_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ScorecardKpisTableAgent())
