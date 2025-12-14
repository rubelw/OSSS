# Auto-generated LangChain agent for QueryData mode="ell_plans"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .ell_plans_table import EllPlansFilters, run_ell_plans_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.ell_plans")

class EllPlansTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `ell_plans`.
    """

    name = "lc.ell_plans_table"
    intent = "ell_plans"
    intent_aliases = ['ell plans', 'ell_plans', 'english learner plans', 'english language learner plans', 'esl plans']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_ell_plans_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(EllPlansTableAgent())
