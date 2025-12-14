# Auto-generated LangChain agent for QueryData mode="evaluation_responses"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .evaluation_responses_table import EvaluationResponsesFilters, run_evaluation_responses_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.evaluation_responses")

class EvaluationResponsesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `evaluation_responses`.
    """

    name = "lc.evaluation_responses_table"
    intent = "evaluation_responses"
    intent_aliases = ['evaluation responses', 'evaluation_responses', 'observation responses', 'rubric responses', 'evaluation answers', 'teacher evaluation responses']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_evaluation_responses_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(EvaluationResponsesTableAgent())
