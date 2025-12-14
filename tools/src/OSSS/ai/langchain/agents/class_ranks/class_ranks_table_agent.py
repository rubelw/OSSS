# Auto-generated LangChain agent for QueryData mode="class_ranks"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .class_ranks_table import ClassRanksFilters, run_class_ranks_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.class_ranks")

class ClassRanksTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `class_ranks`.
    """

    name = "lc.class_ranks_table"
    intent = "class_ranks"
    intent_aliases = ['class ranks', 'class_ranks', 'class rank', 'graduation rank']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_class_ranks_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ClassRanksTableAgent())
