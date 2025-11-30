# OSSS/ai/agents/query_data/handlers/scorecards_handler.py
from __future__ import annotations

from typing import Any, Dict, List
import csv
import httpx
import io
import logging

from OSSS.ai.agents.base import AgentContext
from OSSS.ai.agents.query_data.query_data_registry import (
    QueryHandler,
    FetchResult,
    register_handler,
)

logger = logging.getLogger("OSSS.ai.agents.query_data.scorecards")

API_BASE = "http://host.containers.internal:8081"


# ---------------------------------------------------------------------------
# Low-level fetch
# ---------------------------------------------------------------------------


async def _fetch_scorecards(
    *, skip: int = 0, limit: int = 100
) -> List[Dict[str, Any]]:
    scorecards_url = f"{API_BASE}/api/scorecards"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(scorecards_url, params=params)
            resp.raise_for_status()
            scorecards: List[Dict[str, Any]] = resp.json()
    except Exception as e:
        logger.exception("Error calling scorecards API")
        raise RuntimeError(f"Error querying scorecards API: {e}") from e

    return scorecards


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _build_scorecard_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No scorecards were found in the system."

    header = (
        "| # | Scorecard ID | Plan ID | Name | Created At | Updated At |\n"
        "|---|--------------|---------|------|------------|------------|\n"
    )

    lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        lines.append(
            f"| {idx} | "
            f"{r.get('id', '')} | "
            f"{r.get('plan_id', '')} | "
            f"{r.get('name', '')} | "
            f"{r.get('created_at', '')} | "
            f"{r.get('updated_at', '')} |"
        )

    return header + "\n".join(lines)


def _build_scorecard_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    output = io.StringIO()
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# ---------------------------------------------------------------------------
# Handler implementation
# ---------------------------------------------------------------------------


class ScorecardsHandler(QueryHandler):
    mode = "scorecards"
    keywords = [
        "scorecard",
        "scorecards",
        "plan scores",
        "plan scorecards",
    ]
    source_label = "your DCG OSSS scorecards service"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        scorecards = await _fetch_scorecards(skip=skip, limit=limit)
        return {
            "rows": scorecards,
            "scorecards": scorecards,
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_scorecard_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_scorecard_csv(rows)


# register on import
register_handler(ScorecardsHandler())
