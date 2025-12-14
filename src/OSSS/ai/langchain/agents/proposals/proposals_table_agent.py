# Auto-generated LangChain agent for QueryData mode="proposals"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .proposals_table import ProposalsFilters, run_proposals_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.proposals")

class ProposalsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `proposals`.
    """

    name = "lc.proposals_table"
    intent = "proposals"
    intent_aliases = ['proposals', 'proposal', 'grant proposals', 'DCG proposals', 'OSSS proposals']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_proposals_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ProposalsTableAgent())
