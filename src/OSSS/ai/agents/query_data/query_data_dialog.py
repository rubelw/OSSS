from __future__ import annotations

import logging

from OSSS.ai.agents.base import AgentContext

from .query_data_state import StudentQueryState

logger = logging.getLogger("OSSS.ai.agents.query_data.dialog")


async def evaluate_student_query_slots(
    context: AgentContext,
    state: StudentQueryState,
) -> StudentQueryState:
    """
    Given the AgentContext, decide what skip/limit to use.

    For now we:
      - read optional numeric hints from context.extra / context.tool_input (if present),
      - clamp to reasonable defaults,
      - leave everything else unchanged.

    You can expand this to:
      - parse grade, building, program, etc. from the user utterance,
      - ask follow-up questions, etc.
    """
    # ---- Example: try to pull override values from context.extra/tool_input ----
    skip = getattr(context, "skip", None)
    limit = getattr(context, "limit", None)

    # Some OSSS flows stick things in context.extra or context.tool_input; be defensive.
    extra = getattr(context, "extra", None) or {}
    if skip is None:
        skip = extra.get("skip")
    if limit is None:
        limit = extra.get("limit")

    try:
        if skip is not None:
            state.skip = max(0, int(skip))
    except Exception:
        logger.warning("[query_data.dialog] invalid skip=%r, keeping %s", skip, state.skip)

    try:
        if limit is not None:
            # keep it sane; adjust if you want bigger pages
            state.limit = max(1, min(int(limit), 500))
    except Exception:
        logger.warning("[query_data.dialog] invalid limit=%r, keeping %s", limit, state.limit)

    logger.info(
        "[query_data.dialog] evaluated slots: session_id=%s skip=%s limit=%s",
        state.session_id,
        state.skip,
        state.limit,
    )
    return state
