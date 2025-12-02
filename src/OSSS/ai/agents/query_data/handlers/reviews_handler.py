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
from OSSS.ai.agents.query_data.query_data_errors import QueryDataError

logger = logging.getLogger("OSSS.ai.agents.query_data.reviews")

API_BASE = "http://host.containers.internal:8081"

SAFE_MAX_ROWS = 200  # safety cap for markdown tables


# -------------------------------------------------------------------
# Low-level fetch
# -------------------------------------------------------------------
async def _fetch_reviews(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/reviews"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

    except httpx.HTTPStatusError as e:
        status = (
            e.response.status_code
            if getattr(e, "response", None) is not None
            else "unknown"
        )
        logger.exception("HTTP error calling reviews API")
        raise QueryDataError(
            f"HTTP {status} error querying reviews API: {str(e)}",
            reviews_url=url,
        ) from e

    except Exception as e:
        logger.exception("Error calling reviews API")
        raise QueryDataError(
            f"Error querying reviews API: {str(e)}",
            reviews_url=url,
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected reviews payload type: {type(data)!r}",
            reviews_url=url,
        )

    return data


# -------------------------------------------------------------------
# Formatting helpers
# -------------------------------------------------------------------
def _stringify_cell(v: Any, max_len: int = 120) -> str:
    if v is None:
        return ""
    s = str(v)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


# -------------------------------------------------------------------
# Markdown builder
# -------------------------------------------------------------------
def _build_reviews_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No reviews records were found in the system."

    rows = rows[:SAFE_MAX_ROWS]  # enforce safety

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No reviews records were found in the system."

    # Move id last if present
    if "id" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "id"] + ["id"]

    header_cells = ["#"] + fieldnames

    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    body_lines: List[str] = []

    for idx, r in enumerate(rows, start=1):
        row_cells = [_stringify_cell(idx)]
        row_cells.extend(_stringify_cell(r.get(f, "")) for f in fieldnames)

        body_lines.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(body_lines)


# -------------------------------------------------------------------
# CSV builder
# -------------------------------------------------------------------
def _build_reviews_csv(rows: List[Dict[str, Any]]) -> str:
    """
    Build a CSV string from review rows.

    Assumes rows is a list of dict-like objects (standard FastAPI/ORM JSON).
    """
    if not rows:
        return ""

    # rows should be list[dict]; just grab keys from the first row
    first = rows[0]
    if isinstance(first, dict):
        fieldnames = list(first.keys())
    else:
        # Extremely defensive fallback: try to treat it like a dataclass / obj
        try:
            fieldnames = list(first.__dict__.keys())
        except Exception:
            # Last-ditch: stringify the whole object in a single column
            fieldnames = ["value"]
            rows = [{"value": r} for r in rows]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# -------------------------------------------------------------------
# Handler
# -------------------------------------------------------------------
class ReviewsHandler(QueryHandler):
    mode = "reviews"

    keywords = [
        "reviews",
        "review records",
        "show reviews",
        "list reviews",
        "feedback reviews",
        "dcg reviews",
        "osss reviews",
    ]

    source_label = "your DCG OSSS data service (reviews)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        rows = await _fetch_reviews(skip=skip, limit=limit)
        return {"rows": rows, "reviews": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_reviews_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_reviews_csv(rows)


# Register on import
register_handler(ReviewsHandler())
