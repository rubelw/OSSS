from __future__ import annotations

import logging
from typing import Any, Dict

from OSSS.ai.agents import register_agent
from OSSS.ai.agents.base import AgentContext, AgentResult
from OSSS.ai.agents.query_data.query_data_registry import (
    detect_mode_from_context,
    get_handler,
)
from OSSS.ai.agents.query_data.query_data_errors import QueryDataError

logger = logging.getLogger("OSSS.ai.agents.query_data.agent")


class QueryDataAgentResult:
    """
    Simple AgentResult-like container so the router can use getattr()
    the same way for all agents.
    """

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


# ⬇ Force-import all handlers once so they self-register into the registry.
#    (you can also move this into OSSS.ai.agents.query_data.__init__ if preferred)
from OSSS.ai.agents.query_data.handlers import live_scorings_handler  # noqa: F401
from OSSS.ai.agents.query_data.handlers import students_handler  # noqa: F401
from OSSS.ai.agents.query_data.handlers import scorecards_handler  # noqa: F401
from OSSS.ai.agents.query_data.handlers import materials_handler  # noqa: F401


@register_agent("query_data")
class QueryDataAgent:
    async def run(self, ctx: AgentContext) -> AgentResult:
        skip = 0
        limit = 100

        # Let the registry inspect ctx (including intent_raw_model_output) to decide mode
        mode = detect_mode_from_context(ctx, fallback_mode="students")
        handler = get_handler(mode)
        if handler is None:
            logger.warning(
                "No handler registered for mode=%s, falling back to students", mode
            )
            mode = "students"
            handler = get_handler(mode)

        if handler is None:
            # Absolute last-resort guardrail
            logger.error("No handler found even for fallback 'students' mode")
            return AgentResult(
                answer_text="I couldn't find a data handler for this request.",
                status="error",
                intent=ctx.intent or "query_data",
                agent_id="query_data",
                agent_name="QueryDataAgent",
                data={
                    "agent_debug_information": {
                        "phase": "query_data",
                        "mode": mode,
                        "error": "no_handler_registered",
                    }
                },
            )

        logger.info(
            "QueryDataAgent mode=%s handler=%s",
            mode,
            type(handler).__name__,
        )

        try:
            # Handler contract:
            #   fetch(ctx, skip, limit) -> dict with at least {"rows": [...]}
            fetch_result: Dict[str, Any] = await handler.fetch(ctx, skip, limit)
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
            # keep all handler-specific fields in debug
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

        except QueryDataError as e:
            # Structured error with backend URLs from any handler
            logger.exception("QueryDataAgent encountered QueryDataError")
            lines = [
                "I attempted to query the backend APIs but encountered an error.",
                "",
                str(e),
            ]

            # Optionally attach known URLs if present on the error
            for attr_name, label in [
                ("students_url", "Students URL"),
                ("persons_url", "Persons URL"),
                ("scorecards_url", "Scorecards URL"),
                ("live_scorings_url", "Live scoring URL"),
                ("materials_url", "Materials URL"),
            ]:
                url = getattr(e, attr_name, None)
                if url:
                    lines.append(f"{label}: {url}")

            return AgentResult(
                answer_text="\n".join(lines),
                status="error",
                intent=ctx.intent or "query_data",
                agent_id="query_data",
                agent_name="QueryDataAgent",
                data={
                    "agent_debug_information": {
                        "phase": "query_data",
                        "mode": mode,
                        "error": str(e),
                        "students_url": getattr(e, "students_url", None),
                        "persons_url": getattr(e, "persons_url", None),
                        "scorecards_url": getattr(e, "scorecards_url", None),
                        "live_scorings_url": getattr(e, "live_scorings_url", None),
                        "materials_url": getattr(e, "materials_url", None),
                    }
                },
            )

        except Exception as e:
            logger.exception("QueryDataAgent failed with unexpected error")
            return AgentResult(
                answer_text=(
                    "I attempted to query the backend APIs but encountered an unexpected error."
                ),
                status="error",
                intent=ctx.intent or "query_data",
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
