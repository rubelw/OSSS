# Auto-generated LangChain agent for QueryData mode="evaluation_sections"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .evaluation_sections_table import EvaluationSectionsFilters, run_evaluation_sections_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.evaluation_sections")

class EvaluationSectionsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `evaluation_sections`.
    """

    name = "lc.evaluation_sections_table"
    intent = "evaluation_sections"
    intent_aliases = ['evaluation_sections', 'evaluation sections', 'evaluation rubric sections', 'observation sections', 'teacher evaluation sections']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_evaluation_sections_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(EvaluationSectionsTableAgent())
