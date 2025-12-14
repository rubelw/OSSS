# Auto-generated LangChain agent for QueryData mode="project_tasks"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .project_tasks_table import ProjectTasksFilters, run_project_tasks_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.project_tasks")

class ProjectTasksTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `project_tasks`.
    """

    name = "lc.project_tasks_table"
    intent = "project_tasks"
    intent_aliases = ['project tasks', 'project task list', 'tasks for projects', 'dcg project tasks', 'osss project tasks', 'district project tasks']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_project_tasks_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(ProjectTasksTableAgent())
