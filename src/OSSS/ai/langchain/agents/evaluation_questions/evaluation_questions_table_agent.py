# Auto-generated LangChain agent for QueryData mode="evaluation_questions"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .evaluation_questions_table import EvaluationQuestionsFilters, run_evaluation_questions_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.evaluation_questions")

class EvaluationQuestionsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `evaluation_questions`.
    """

    name = "lc.evaluation_questions_table"
    intent = "evaluation_questions"
    intent_aliases = ['evaluation questions', 'evaluation_questions', 'evaluation rubric questions', 'observation questions', 'teacher evaluation questions']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_evaluation_questions_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(EvaluationQuestionsTableAgent())
