from __future__ import annotations

from typing import Any, Dict, List, Sequence
import httpx
import csv
import io
import logging
import os

from OSSS.ai.agents.base import AgentContext
from OSSS.ai.agents.query_data.query_data_registry import (
    QueryHandler,
    FetchResult,
    register_handler,
)
from OSSS.ai.agents.query_data.query_data_errors import QueryDataError

logger = logging.getLogger("OSSS.ai.agents.query_data.proposal_reviews")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE = os.getenv("OSSS_REVIEWS_API_BASE", "http://host.containers.internal:8081")
PROPOSAL_REVIEWS_ENDPOINT = "/api/proposal_reviews"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------

async def _fetch_proposal_reviews(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}{PROPOSAL_REVIEWS_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug("Fetching proposal_reviews from %s params=%s", url, params)

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            try:
                data = resp.json()
            except ValueError as json_err:
                logger.exception("Failed to decode proposal_reviews JSON")
                raise QueryDataError(
                    f"Error decoding proposal_reviews JSON: {json_err}",
                    proposal_reviews_url=url,
                ) from json_err

    except httpx.RequestError as e:
        logger.exception("Network error calling proposal_reviews API")
        raise QueryDataError(
            f"Network error querying proposal_reviews API: {e}",
            proposal_reviews_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status_code = getattr(e.response, "status_code", None)
        logger.exception(
            "proposal_reviews API returned HTTP %s", status_code
        )
        raise QueryDataError(
            f"proposal_reviews API returned HTTP {status_code}",
            proposal_reviews_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling proposal_reviews API")
        raise QueryDataError(
            f"Unexpected error querying proposal_reviews API: {e}",
            proposal_reviews_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected proposal_reviews payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected proposal_reviews payload type: {type(data)!r}",
            proposal_reviews_url=url,
        )

    # Filter non-dict items defensively
    cleaned = [item for item in data if isinstance(item, dict)]
    return cleaned


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _escape_md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_fieldnames(rows: Sequence[Dict[str, Any]]) -> List[str]:
    if not rows:
        return []

    preferred = [
        "id",
        "proposal_id",
        "reviewer",
        "score",
        "status",
        "created_at",
        "updated_at",
    ]

    all_keys = list({k for row in rows for k in row.keys()})

    ordered = [k for k in preferred if k in all_keys]
    for k in all_keys:
        if k not in ordered:
            ordered.append(k)

    return ordered


# ---------------------------------------------------------------------------
# Markdown + CSV
# ---------------------------------------------------------------------------

def _build_proposal_reviews_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No proposal_reviews records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    fields = _select_fieldnames(display)
    if not fields:
        return "No proposal_reviews records were found in the system."

    header_cells = ["#"] + fields
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    lines = []
    for idx, row in enumerate(display, start=1):
        cells = [_escape_md(idx)] + [_escape_md(row.get(f, "")) for f in fields]
        lines.append("| " + " | ".join(cells) + " |")

    table = header + separator + "\n".join(lines)

    if total > MAX_MARKDOWN_ROWS:
        table += (
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of {total} proposal review records. "
            "Request CSV to download the full dataset._"
        )

    return table


def _build_proposal_reviews_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]

    fields = _select_fieldnames(display)
    if not fields:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(display)

    csv_text = output.getvalue()

    if total > MAX_CSV_ROWS:
        csv_text += f"# Truncated to first {MAX_CSV_ROWS} of {total} rows\n"

    return csv_text


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

class ProposalReviewsHandler(QueryHandler):
    mode = "proposal_reviews"
    keywords = [
        "proposal reviews",
        "reviews of proposals",
        "proposal review list",
        "dcg proposal reviews",
        "osss proposal reviews",
        "review scores",
        "grant proposal reviews",
    ]
    source_label = "DCG OSSS data service (proposal_reviews)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:

        logger.debug(
            "ProposalReviewsHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip, limit, getattr(ctx, "user_id", None)
        )

        rows = await _fetch_proposal_reviews(skip=skip, limit=limit)

        return {
            "rows": rows,
            "proposal_reviews": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_proposal_reviews_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_proposal_reviews_csv(rows)


register_handler(ProposalReviewsHandler())
