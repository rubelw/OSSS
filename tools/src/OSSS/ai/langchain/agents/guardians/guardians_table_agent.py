# Auto-generated LangChain agent for QueryData mode="guardians"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .guardians_table import GuardiansFilters, run_guardians_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.guardians")

class GuardiansTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `guardians`.
    """

    name = "lc.guardians_table"
    intent = "guardians"
    intent_aliases = ['guardians', 'student guardians', 'parent contacts', 'family contacts', 'guardian list']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_guardians_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(GuardiansTableAgent())
