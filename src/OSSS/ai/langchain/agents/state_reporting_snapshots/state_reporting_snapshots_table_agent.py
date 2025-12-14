# Auto-generated LangChain agent for QueryData mode="state_reporting_snapshots"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .state_reporting_snapshots_table import StateReportingSnapshotsFilters, run_state_reporting_snapshots_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.state_reporting_snapshots")

class StateReportingSnapshotsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `state_reporting_snapshots`.
    """

    name = "lc.state_reporting_snapshots_table"
    intent = "state_reporting_snapshots"
    intent_aliases = ['state_reporting_snapshots', 'state reporting snapshots', 'state reporting snapshot', 'state reporting export', 'state reporting submission']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_state_reporting_snapshots_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(StateReportingSnapshotsTableAgent())
