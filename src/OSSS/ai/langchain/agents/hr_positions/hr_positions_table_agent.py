# Auto-generated LangChain agent for QueryData mode="hr_positions"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .hr_positions_table import HrPositionsFilters, run_hr_positions_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.hr_positions")

class HrPositionsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `hr_positions`.
    """

    name = "lc.hr_positions_table"
    intent = "hr_positions"
    intent_aliases = ['hr positions', 'hr_positions', 'job positions', 'position catalog', 'staff positions']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_hr_positions_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(HrPositionsTableAgent())
