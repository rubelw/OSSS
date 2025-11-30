from __future__ import annotations

import logging
from typing import Any, Dict

from OSSS.ai.agents import register_agent
from OSSS.ai.agents.base import AgentContext, AgentResult
from OSSS.ai.agents.query_data.query_data_registry import (
    detect_mode_from_context,
    get_handler,
)

logger = logging.getLogger("OSSS.ai.agents.query_data.agent")


class QueryDataAgentResult:
    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


# ⬇ Force-import all handlers once so they self-register
#    (you can keep this in __init__.py of the package instead)
from OSSS.ai.agents.query_data.handlers import live_scorings_handler  # noqa: F401
from OSSS.ai.agents.query_data.handlers import students_handler  # noqa: F401
from OSSS.ai.agents.query_data.handlers import scorecards_handler  # noqa: F401


@register_agent("query_data")
class QueryDataAgent:
    async def run(self, ctx: AgentContext) -> AgentResult:
        skip = 0
        limit = 100

        mode = detect_mode_from_context(ctx, fallback_mode="students")
        handler = get_handler(mode)
        if handler is None:
            logger.warning("No handler registered for mode=%s, falling back to students", mode)
            mode = "students"
            handler = get_handler(mode)

        logger.info("QueryDataAgent mode=%s handler=%s", mode, type(handler).__name__)

        try:
            fetch_result = await handler.fetch(ctx, skip, limit)
            rows = fetch_result.get("rows", [])

            markdown_table = handler.to_markdown(rows)
            csv_data = handler.to_csv(rows)

            debug_info: Dict[str, Any] = {
                "phase": "query_data",
                "mode": mode,
                "row_count": len(rows),
                "csv": csv_data,
                "csv_filename": f"{mode}_export.csv",
            }
            debug_info.update(fetch_result)

            answer = (
                markdown_table
                + f"\n\n---\n\nThis data is coming from {handler.source_label}."
            )

            return QueryDataAgentResult(
                status="ok",
                answer_text=answer,
                extra_chunks=[],
                intent=ctx.intent or "query_data",
                data={"agent_debug_information": debug_info},
                agent_id="query_data",
                agent_name="QueryDataAgent",
            )

        except Exception as e:
            logger.exception("query_data_tool failed")
            # you can still use your QueryDataError with URLs here if you like
            return AgentResult(
                answer_text="I attempted to query the backend APIs but encountered an error.",
                status="error",
                intent="query_data",
                agent_id="query_data",
                agent_name="QueryDataAgent",
                data={
                    "agent_debug_information": {
                        "phase": "query_data",
                        "mode": mode,
                        "error": str(e),
                    }
                },
            )
