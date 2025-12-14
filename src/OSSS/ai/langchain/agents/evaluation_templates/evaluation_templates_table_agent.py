# Auto-generated LangChain agent for QueryData mode="evaluation_templates"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .evaluation_templates_table import EvaluationTemplatesFilters, run_evaluation_templates_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.evaluation_templates")

class EvaluationTemplatesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `evaluation_templates`.
    """

    name = "lc.evaluation_templates_table"
    intent = "evaluation_templates"
    intent_aliases = ['evaluation_templates', 'evaluation templates', 'teacher evaluation templates', 'observation templates', 'performance evaluation templates']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_evaluation_templates_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(EvaluationTemplatesTableAgent())
