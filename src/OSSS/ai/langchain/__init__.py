# src/OSSS/ai/langchain/__init__.py
from __future__ import annotations

from typing import Any, Dict, Awaitable, Callable
import logging

from OSSS.ai.langchain.agents.student_info_table import run_student_info_table

logger = logging.getLogger("OSSS.ai.langchain")

# Map high-level intents to LangChain agent names
INTENT_TO_LC_AGENT: dict[str, str] = {
    "langchain_agent": "lc.student_info_table",        # bridge from old behavior
    "student_info": "lc.student_info_table",
    #"students_missing_assignments": "lc.students_missing_assignments",
    # add more as you build them...
}

# Map LangChain agent names -> concrete callables
LC_AGENTS: dict[str, Callable[..., Awaitable[Dict[str, Any]]]] = {
    "lc.student_info_table": run_student_info_table,
    # "lc.students_missing_assignments": run_students_missing_assignments,
}


async def run_agent(
    *,
    message: str,
    session_id: str,
    agent_name: str,
) -> Dict[str, Any]:
    """
    Single entry-point used by RouterAgent.

    The router passes in the logical `agent_name` (e.g. "lc.student_info_table"),
    we look up the concrete async function and invoke it.
    """
    logger.info(
        "LangChain.run_agent called: session_id=%s agent_name=%s message=%r",
        session_id,
        agent_name,
        message,
    )

    fn = LC_AGENTS.get(agent_name)
    if fn is None:
        logger.warning("LangChain: unknown agent %s", agent_name)
        return {
            "reply": f"[LC] Unknown agent: {agent_name}",
        }

    return await fn(message=message, session_id=session_id)
