# Auto-generated LangChain agent for QueryData mode="agenda_workflow_steps"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .agenda_workflow_steps_table import AgendaWorkflowStepsFilters, run_agenda_workflow_steps_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.agenda_workflow_steps")

class AgendaWorkflowStepsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `agenda_workflow_steps`.
    """

    name = "lc.agenda_workflow_steps_table"
    intent = "agenda_workflow_steps"
    intent_aliases = ['agenda workflow steps', 'agenda_workflow_steps', 'agenda approval steps']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_agenda_workflow_steps_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(AgendaWorkflowStepsTableAgent())
