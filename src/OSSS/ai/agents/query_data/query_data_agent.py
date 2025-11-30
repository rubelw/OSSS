from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, TypedDict

from OSSS.ai.agents import register_agent
from OSSS.ai.agents.base import AgentContext, AgentResult

# ⬇⬇ FIXED IMPORTS: use the query_data package
from .query_data_datasources import (
    QueryDataError,
    query_live_scorings_tool,
    query_scorecards_tool,
    query_students_tool,
)
from .query_data_formatters import (
    build_live_scorings_csv,
    build_live_scorings_markdown_table,
    build_scorecard_csv,
    build_scorecard_markdown_table,
    build_student_csv,
    build_student_markdown_table,
)

logger = logging.getLogger("OSSS.ai.agents.query_data.agent")

# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

MODE_STUDENTS = "students"
MODE_PERSONS = "persons"  # currently treated same as students combined
MODE_SCORECARDS = "scorecards"
MODE_LIVE_SCORINGS = "live_scorings"


class QueryDataAgentResult:
    """Simple AgentResult-like container used by QueryDataAgent."""

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class FetchResult(TypedDict, total=False):
    """What each fetch_... function should return for the agent."""
    rows: List[Dict[str, Any]]
    students: List[Dict[str, Any]]
    persons: List[Dict[str, Any]]
    combined_rows: List[Dict[str, Any]]
    scorecards: List[Dict[str, Any]]
    live_scorings: List[Dict[str, Any]]


FetchFn = Callable[[int, int], Awaitable[FetchResult]]
MarkdownFn = Callable[[List[Dict[str, Any]]], str]
CsvFn = Callable[[List[Dict[str, Any]]], str]


@dataclass
class ModeConfig:
    mode: str
    fetch: FetchFn
    to_markdown: MarkdownFn
    to_csv: CsvFn
    source_label: str
    debug_rows_key: str


async def _fetch_mode_students(skip: int, limit: int) -> FetchResult:
    data = await query_students_tool(skip=skip, limit=limit)
    return {
        "rows": data["combined_rows"],
        "students": data["students"],
        "persons": data["persons"],
        "combined_rows": data["combined_rows"],
    }


async def _fetch_mode_scorecards(skip: int, limit: int) -> FetchResult:
    scorecards = await query_scorecards_tool(skip=skip, limit=limit)
    return {
        "rows": scorecards,
        "scorecards": scorecards,
    }


async def _fetch_mode_live_scorings(skip: int, limit: int) -> FetchResult:
    live_scorings = await query_live_scorings_tool(skip=skip, limit=limit)
    return {
        "rows": live_scorings,
        "live_scorings": live_scorings,
    }


MODE_CONFIGS: dict[str, ModeConfig] = {
    MODE_STUDENTS: ModeConfig(
        mode=MODE_STUDENTS,
        fetch=_fetch_mode_students,
        to_markdown=build_student_markdown_table,
        to_csv=build_student_csv,
        source_label="your DCG OSSS demo student/person service",
        debug_rows_key="combined",
    ),
    MODE_SCORECARDS: ModeConfig(
        mode=MODE_SCORECARDS,
        fetch=_fetch_mode_scorecards,
        to_markdown=build_scorecard_markdown_table,
        to_csv=build_scorecard_csv,
        source_label="your DCG OSSS scorecards service",
        debug_rows_key="scorecards",
    ),
    MODE_LIVE_SCORINGS: ModeConfig(
        mode=MODE_LIVE_SCORINGS,
        fetch=_fetch_mode_live_scorings,
        to_markdown=build_live_scorings_markdown_table,
        to_csv=build_live_scorings_csv,
        source_label="your DCG OSSS live scoring service",
        debug_rows_key="live_scorings",
    ),
}

KEYWORD_MODE_MAP: dict[str, str] = {
    "scorecard": MODE_SCORECARDS,
    "scorecards": MODE_SCORECARDS,
    "live scoring": MODE_LIVE_SCORINGS,
    "live score": MODE_LIVE_SCORINGS,
    "live scores": MODE_LIVE_SCORINGS,
    "live game": MODE_LIVE_SCORINGS,
}


def _detect_mode_from_context(ctx: AgentContext) -> str:
    """Decide which dataset mode to use based on classifier metadata and text."""
    q = (ctx.query or "").lower()

    meta_mode: str | None = None
    raw = ctx.metadata.get("intent_raw_model_output") if ctx.metadata else None
    if isinstance(raw, str):
        try:
            obj = json.loads(raw)
            heuristic_rule = obj.get("heuristic_rule") or {}
            metadata = heuristic_rule.get("metadata") or {}
            meta_mode = metadata.get("mode")
        except Exception:
            logger.exception(
                "QueryDataAgent: failed to parse intent_raw_model_output", exc_info=True
            )

    if meta_mode in MODE_CONFIGS:
        logger.info("QueryDataAgent: using mode from classifier metadata: %s", meta_mode)
        return meta_mode

    for key, mode in KEYWORD_MODE_MAP.items():
        if key in q:
            return mode

    return MODE_STUDENTS


@register_agent("query_data")
class QueryDataAgent:
    async def run(self, ctx: AgentContext) -> AgentResult:
        skip = 0
        limit = 100

        mode = _detect_mode_from_context(ctx)
        cfg = MODE_CONFIGS.get(mode, MODE_CONFIGS[MODE_STUDENTS])
        logger.info("QueryDataAgent mode=%s", cfg.mode)

        try:
            fetch_result = await cfg.fetch(skip, limit)
            rows = fetch_result.get("rows", [])

            markdown_table = cfg.to_markdown(rows)
            csv_data = cfg.to_csv(rows)

            debug_info: Dict[str, Any] = {
                "phase": "query_data",
                "mode": cfg.mode,
                "row_count": len(rows),
                "csv": csv_data,
                "csv_filename": f"{cfg.mode}_export.csv",
            }
            debug_info.update(fetch_result)

            answer = (
                markdown_table
                + f"\n\n---\n\nThis data is coming from {cfg.source_label}."
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
            logger.exception("query_data_tool failed")
            lines = [
                "I attempted to query the backend APIs but encountered an error.",
                "",
            ]
            if e.students_url:
                lines.append(f"Students URL: {e.students_url}")
            if e.persons_url:
                lines.append(f"Persons URL: {e.persons_url}")
            if e.scorecards_url:
                lines.append(f"Scorecards URL: {e.scorecards_url}")
            if e.live_scorings_url:
                lines.append(f"Live scoring URL: {e.live_scorings_url}")

            return AgentResult(
                answer_text="\n".join(lines),
                status="error",
                intent="query_data",
                agent_id="query_data",
                agent_name="QueryDataAgent",
                data={
                    "agent_debug_information": {
                        "phase": "query_data",
                        "error": str(e),
                        "students_url": e.students_url,
                        "persons_url": e.persons_url,
                        "scorecards_url": e.scorecards_url,
                        "live_scorings_url": e.live_scorings_url,
                        "mode": mode,
                    }
                },
            )
