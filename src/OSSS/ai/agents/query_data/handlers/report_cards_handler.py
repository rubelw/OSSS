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

logger = logging.getLogger("OSSS.ai.agents.query_data.report_cards")

API_BASE = "http://host.containers.internal:8081"


async def _fetch_report_cards(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/report_cards"
    params = {"skip": skip, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.exception("Error calling report_cards API")
        raise QueryDataError(
            f"Error querying report_cards API: {e}",
            report_cards_url=url,
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected report_cards payload type: {type(data)!r}",
            report_cards_url=url,
        )
    return data


def _build_report_cards_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No report_cards records were found in the system."

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No report_cards records were found in the system."

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        row_cells = [str(idx)] + [str(r.get(f, "")) for f in fieldnames]
        lines.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(lines)


def _build_report_cards_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    fieldnames = list(rows[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


class ReportCardsHandler(QueryHandler):
    mode = "report_cards"
    keywords = [
        "report_cards",
        "report cards",
    ]
    source_label = "your DCG OSSS data service (report_cards)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        rows = await _fetch_report_cards(skip=skip, limit=limit)
        return {"rows": rows, "report_cards": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_report_cards_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_report_cards_csv(rows)


# register on import
register_handler(ReportCardsHandler())
