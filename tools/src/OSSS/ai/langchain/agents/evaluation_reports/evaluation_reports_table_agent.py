# Auto-generated LangChain agent for QueryData mode="evaluation_reports"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .evaluation_reports_table import EvaluationReportsFilters, run_evaluation_reports_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.evaluation_reports")

class EvaluationReportsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `evaluation_reports`.
    """

    name = "lc.evaluation_reports_table"
    intent = "evaluation_reports"
    intent_aliases = ['evaluation reports', 'evaluation_reports', 'teacher evaluation reports', 'observation reports', 'performance evaluation reports']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_evaluation_reports_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(EvaluationReportsTableAgent())
