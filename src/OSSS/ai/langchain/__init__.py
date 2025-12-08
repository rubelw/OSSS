# src/OSSS/ai/langchain/__init__.py
from __future__ import annotations

from typing import Any, Dict
import logging

from OSSS.ai.langchain.agents.student_info_table_agent import StudentInfoTableAgent
from OSSS.ai.langchain.registry import (
    register_langchain_agent,
    run_agent as registry_run_agent,
)

logger = logging.getLogger("OSSS.ai.langchain")

# ---------------------------------------------------------------------------
# Intent → LangChain agent name mapping
# ---------------------------------------------------------------------------

INTENT_TO_LC_AGENT: dict[str, str] = {
    # bridge from old behavior: generic "langchain_agent" goes to student_info_table
    "langchain_agent": "lc.student_info_table",
    "student_info": "lc.student_info_table",
    # "students_missing_assignments": "lc.students_missing_assignments",
    # add more as you build them...
}

# ---------------------------------------------------------------------------
# Register concrete agents with the registry
# ---------------------------------------------------------------------------

# Student info table agent (uses the StructuredTool internally)
register_langchain_agent(StudentInfoTableAgent())

# add more agents here as you implement them:
# from OSSS.ai.langchain.agents.students_missing_assignments_agent import (
#     StudentsMissingAssignmentsAgent,
# )
# register_langchain_agent(StudentsMissingAssignmentsAgent())


# ---------------------------------------------------------------------------
# Public entry point used by RouterAgent
# ---------------------------------------------------------------------------

async def run_agent(
    *,
    message: str,
    session_id: str,
    agent_name: str,
) -> Dict[str, Any]:
    """
    Single entry-point used by RouterAgent.

    The router passes in the logical `agent_name` (e.g. "lc.student_info_table"),
    we delegate to the registry, which looks up the registered LangChain agent
    object and calls its `run(...)` method.
    """
    logger.info(
        "LangChain.run_agent called: session_id=%s agent_name=%s message=%r",
        session_id,
        agent_name,
        message,
    )

    # Delegate to the registry implementation
    return await registry_run_agent(
        message=message,
        session_id=session_id,
        agent_name=agent_name,
    )
