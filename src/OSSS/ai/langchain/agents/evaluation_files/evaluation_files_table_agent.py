# Auto-generated LangChain agent for QueryData mode="evaluation_files"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .evaluation_files_table import EvaluationFilesFilters, run_evaluation_files_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.evaluation_files")

class EvaluationFilesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `evaluation_files`.
    """

    name = "lc.evaluation_files_table"
    intent = "evaluation_files"
    intent_aliases = ['evaluation files', 'evaluation_files', 'evaluation artifacts', 'observation artifacts', 'evaluation attachments']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_evaluation_files_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(EvaluationFilesTableAgent())
