from __future__ import annotations

import logging
from typing import Any, Dict

from OSSS.ai.agents import register_agent
from OSSS.ai.agents.base import AgentContext, AgentResult
from OSSS.ai.agents.query_data.handler_loader import load_all_query_handlers
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


# ------------------------------------------------------------------------------
# Load ALL query handlers BEFORE the agent is registered
# This auto-imports everything in handlers/*.py safely.
# ------------------------------------------------------------------------------
load_all_query_handlers()


@register_agent("query_data")
class QueryDataAgent:
    async def run(self, ctx: AgentContext) -> AgentResult:
        skip = 0
        limit = 100

        # Decide which handler to use based on intent/keywords
        mode = detect_mode_from_context(ctx, fallback_mode="students")
        handler = get_handler(mode)

        if handler is None:
            logger.warning("No handler registered for mode=%s; falling back to students", mode)
            mode = "students"
            handler = get_handler(mode)

        if handler is None:
            # Nothing to fallback to → major configuration error
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

        logger.info("QueryDataAgent mode=%s handler=%s", mode, type(handler).__name__)

        try:
            # Execute handler-level query
            fetch_result: Dict[str, Any] = await handler.fetch(ctx, skip, limit)
            rows = fetch_result.get("rows", [])

            # Convert to output formats
            markdown_table = handler.to_markdown(rows)
            csv_data = handler.to_csv(rows)

            # Diagnostics
            debug_info: Dict[str, Any] = {
                "phase": "query_data",
                "mode": mode,
                "row_count": len(rows),
                "csv": csv_data,
                "csv_filename": f"{mode}_export.csv",
                **fetch_result,
            }

            answer = markdown_table + (
                f"\n\n---\n\nThis data is coming from {handler.source_label}."
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
            logger.exception("QueryDataAgent encountered QueryDataError")

            return AgentResult(
                answer_text=(
                    "I attempted to query the backend APIs but encountered an error.\n\n"
                    f"{e}"
                ),
                status="error",
                intent=ctx.intent or "query_data",
                agent_id="query_data",
                agent_name="QueryDataAgent",
                data={"agent_debug_information": {
                    "phase": "query_data",
                    "mode": mode,
                    "error": str(e),
                }},
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
                data={"agent_debug_information": {
                    "phase": "query_data",
                    "mode": mode,
                    "error": str(e),
                }},
            )
