# Auto-generated LangChain agent for QueryData mode="behavior_codes"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .behavior_codes_table import BehaviorCodesFilters, run_behavior_codes_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.behavior_codes")

class BehaviorCodesTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `behavior_codes`.
    """

    name = "lc.behavior_codes_table"
    intent = "behavior_codes"
    intent_aliases = ['behavior codes', 'behavior_codes', 'discipline codes', 'incident codes']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_behavior_codes_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(BehaviorCodesTableAgent())
