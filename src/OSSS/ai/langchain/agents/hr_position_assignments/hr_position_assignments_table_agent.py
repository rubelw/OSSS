# Auto-generated LangChain agent for QueryData mode="hr_position_assignments"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .hr_position_assignments_table import HrPositionAssignmentsFilters, run_hr_position_assignments_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.hr_position_assignments")

class HrPositionAssignmentsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `hr_position_assignments`.
    """

    name = "lc.hr_position_assignments_table"
    intent = "hr_position_assignments"
    intent_aliases = ['hr position assignments', 'hr_position_assignments', 'staff assignments', 'position assignments', 'who is in this position']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_hr_position_assignments_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(HrPositionAssignmentsTableAgent())
