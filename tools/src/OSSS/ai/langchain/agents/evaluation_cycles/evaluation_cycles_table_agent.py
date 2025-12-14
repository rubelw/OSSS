# Auto-generated LangChain agent for QueryData mode="evaluation_cycles"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .evaluation_cycles_table import EvaluationCyclesFilters, run_evaluation_cycles_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.evaluation_cycles")

class EvaluationCyclesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `evaluation_cycles`.
    """

    name = "lc.evaluation_cycles_table"
    intent = "evaluation_cycles"
    intent_aliases = ['evaluation cycles', 'evaluation_cycles', 'evaluation cycle schedule', 'teacher evaluation cycles', 'observation cycles']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_evaluation_cycles_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(EvaluationCyclesTableAgent())
