# Auto-generated LangChain agent for QueryData mode="agenda_workflows"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .agenda_workflows_table import AgendaWorkflowsFilters, run_agenda_workflows_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.agenda_workflows")

class AgendaWorkflowsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `agenda_workflows`.
    """

    name = "lc.agenda_workflows_table"
    intent = "agenda_workflows"
    intent_aliases = ['agenda_workflows', 'agenda workflows', 'board agenda workflows']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_agenda_workflows_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(AgendaWorkflowsTableAgent())
