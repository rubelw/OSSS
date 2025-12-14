# Auto-generated LangChain agent for QueryData mode="evaluation_signoffs"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .evaluation_signoffs_table import EvaluationSignoffsFilters, run_evaluation_signoffs_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.evaluation_signoffs")

class EvaluationSignoffsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `evaluation_signoffs`.
    """

    name = "lc.evaluation_signoffs_table"
    intent = "evaluation_signoffs"
    intent_aliases = ['evaluation_signoffs', 'evaluation signoffs', 'evaluation approvals', 'observation signoffs', 'teacher evaluation signoffs']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_evaluation_signoffs_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(EvaluationSignoffsTableAgent())
