from __future__ import annotations

import logging
import pkgutil
import importlib
from typing import Any, Dict

from OSSS.ai.agents.query_data.handler_loader import load_all_query_handlers
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


# ------------------------------------------------------------------------------
# AUTO-DISCOVER AND IMPORT ALL HANDLER MODULES
# Ensures every handler file is imported and thus self-registers.
# ------------------------------------------------------------------------------

def _import_all_handlers() -> None:
    """
    Dynamically import all modules inside:
        OSSS.ai.agents.query_data.handlers
    so that each handler can call register_handler() at import time.
    """
    import OSSS.ai.agents.query_data.handlers as handler_package

    package_path = handler_package.__path__
    package_name = handler_package.__name__

    for module_info in pkgutil.iter_modules(package_path):
        module_name = f"{package_name}.{module_info.name}"
        try:
            importlib.import_module(module_name)
            logger.debug("Loaded QueryData handler module: %s", module_name)
        except Exception as e:
            logger.exception("Failed to import handler module %s: %s", module_name, e)


# Load handlers AFTER agent registry exists
load_all_query_handlers()


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
            logger.exception("QueryDataAgent encountered QueryDataError")

            lines = [
                "I attempted to query the backend APIs but encountered an error.",
                "",
                str(e),
            ]

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
