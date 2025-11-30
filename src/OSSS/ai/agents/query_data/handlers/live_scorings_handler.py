# OSSS/ai/agents/query_data/handlers/live_scorings_handler.py
from __future__ import annotations

from typing import Any, Dict, List
import httpx
import csv
import io
import logging

from OSSS.ai.agents.base import AgentContext
from OSSS.ai.agents.query_data.query_data_registry import (
    QueryHandler,
    FetchResult,
    register_handler,
)
from OSSS.ai.agents.query_data.query_data_errors import QueryDataError  # optional

logger = logging.getLogger("OSSS.ai.agents.query_data.live_scorings")

API_BASE = "http://host.containers.internal:8081"


async def _fetch_live_scorings(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/live_scorings"
    params = {"skip": skip, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.exception("Error calling live_scorings API")
        raise QueryDataError(
            f"Error querying live_scorings API: {e}",
            live_scorings_url=url,
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected live_scorings payload type: {type(data)!r}",
            live_scorings_url=url,
        )
    return data


def _build_live_scorings_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No live scoring records were found in the system."

    header = (
        "| # | Game ID | Score | Status | Created At | Updated At | Live Scoring ID |\n"
        "|---|---------|-------|--------|------------|------------|-----------------|\n"
    )

    lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        lines.append(
            f"| {idx} | "
            f"{r.get('game_id', '')} | "
            f"{r.get('score', '')} | "
            f"{r.get('status', '')} | "
            f"{r.get('created_at', '')} | "
            f"{r.get('updated_at', '')} | "
            f"{r.get('id', '')} |"
        )

    return header + "\n".join(lines)


def _build_live_scorings_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    output = io.StringIO()
    fieldnames = ["game_id", "score", "status", "created_at", "updated_at", "id"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


class LiveScoringsHandler(QueryHandler):
    mode = "live_scorings"
    keywords = [
        "live scoring",
        "live score",
        "live scores",
        "live game",
    ]
    source_label = "your DCG OSSS live scoring service"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        rows = await _fetch_live_scorings(skip=skip, limit=limit)
        return {"rows": rows, "live_scorings": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_live_scorings_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_live_scorings_csv(rows)


# register on import
register_handler(LiveScoringsHandler())
