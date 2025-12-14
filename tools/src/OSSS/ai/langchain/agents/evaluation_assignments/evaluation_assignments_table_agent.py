# Auto-generated LangChain agent for QueryData mode="evaluation_assignments"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .evaluation_assignments_table import EvaluationAssignmentsFilters, run_evaluation_assignments_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.evaluation_assignments")

class EvaluationAssignmentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `evaluation_assignments`.
    """

    name = "lc.evaluation_assignments_table"
    intent = "evaluation_assignments"
    intent_aliases = ['evaluation assignments', 'evaluation_assignments', 'assigned evaluations', 'evaluator assignments', 'evaluatee assignments']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_evaluation_assignments_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(EvaluationAssignmentsTableAgent())
