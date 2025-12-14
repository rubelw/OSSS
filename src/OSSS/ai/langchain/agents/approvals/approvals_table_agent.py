# Auto-generated LangChain agent for QueryData mode="approvals"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .approvals_table import ApprovalsFilters, run_approvals_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.approvals")

class ApprovalsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `approvals`.
    """

    name = "lc.approvals_table"
    intent = "approvals"
    intent_aliases = ['approvals', 'approval queue', 'pending approvals']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_approvals_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ApprovalsTableAgent())
