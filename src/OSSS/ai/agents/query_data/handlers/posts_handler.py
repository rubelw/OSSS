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
from OSSS.ai.agents.query_data.query_data_errors import QueryDataError  # optional

logger = logging.getLogger("OSSS.ai.agents.query_data.posts")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE = os.getenv(
    "OSSS_POSTS_API_BASE",
    "http://host.containers.internal:8081",
)
POSTS_ENDPOINT = "/api/posts"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


# ---------------------------------------------------------------------------
# Low-level API client
# ---------------------------------------------------------------------------

async def _fetch_posts(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Call the posts API and return a list of post dicts.

    Raises:
        QueryDataError: if the HTTP call fails or the payload is unexpected.
    """
    url = f"{API_BASE}{POSTS_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching posts from %s with params skip=%s, limit=%s",
        url,
        skip,
        limit,
    )

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            verify=False,  # internal dev; tighten in prod
        ) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            try:
                data = resp.json()
            except ValueError as json_err:
                logger.exception("Failed to decode posts API JSON")
                raise QueryDataError(
                    f"Error decoding posts API JSON: {json_err}",
                    posts_url=url,
                ) from json_err

    except httpx.RequestError as e:
        logger.exception("Network error calling posts API")
        raise QueryDataError(
            f"Network error querying posts API: {e}",
            posts_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("posts API returned HTTP %s", status)
        raise QueryDataError(
            f"posts API returned HTTP {status}",
            posts_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling posts API")
        raise QueryDataError(
            f"Unexpected error querying posts API: {e}",
            posts_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected posts payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected posts payload type: {type(data)!r}",
            posts_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in posts payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d posts records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------

def _escape_markdown_cell(value: Any) -> str:
    """
    Escape characters that may break Markdown tables.
    """
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_fieldnames(rows: Sequence[Dict[str, Any]]) -> List[str]:
    """
    Derive a stable field order for posts.
    """
    if not rows:
        return []

    preferred_order = [
        "id",
        "external_id",
        "title",
        "slug",
        "body",
        "summary",
        "status",
        "visibility",
        "category",
        "project_id",
        "proposal_id",
        "created_at",
        "updated_at",
        "published_at",
    ]

    all_keys: List[str] = []
    for r in rows:
        for k in r.keys():
            if k not in all_keys:
                all_keys.append(k)

    ordered: List[str] = []
    for col in preferred_order:
        if col in all_keys:
            ordered.append(col)

    for col in all_keys:
        if col not in ordered:
            ordered.append(col)

    return ordered


# ---------------------------------------------------------------------------
# Markdown + CSV builders
# ---------------------------------------------------------------------------

def _build_posts_markdown_table(rows: List[Dict[str, Any]]) -> str:
    """
    Convert posts rows to a Markdown table, truncating if needed.
    """
    if not rows:
        return "No posts records were found in the system."

    total_rows = len(rows)
    display_rows = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_fieldnames(display_rows)
    if not fieldnames:
        return "No posts records were found in the system."

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    lines: List[str] = []
    for idx, r in enumerate(display_rows, start=1):
        row_cells = [_escape_markdown_cell(idx)] + [
            _escape_markdown_cell(r.get(f, "")) for f in fieldnames
        ]
        lines.append("| " + " | ".join(row_cells) + " |")

    table = header + separator + "\n".join(lines)

    if total_rows > MAX_MARKDOWN_ROWS:
        table += (
            "\n\n"
            f"_Showing first {MAX_MARKDOWN_ROWS} of {total_rows} posts. "
            "You can request CSV to see the full dataset._"
        )

    return table


def _build_posts_csv(rows: List[Dict[str, Any]]) -> str:
    """
    Convert posts rows to CSV, truncating if needed.
    """
    if not rows:
        return ""

    total_rows = len(rows)
    display_rows = rows[:MAX_CSV_ROWS]

    fieldnames = _select_fieldnames(display_rows)
    if not fieldnames:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(display_rows)

    csv_text = output.getvalue()

    if total_rows > MAX_CSV_ROWS:
        csv_text += (
            f"# Truncated to first {MAX_CSV_ROWS} of {total_rows} post rows\n"
        )

    return csv_text


# ---------------------------------------------------------------------------
# Query handler
# ---------------------------------------------------------------------------

class PostsHandler(QueryHandler):
    """
    QueryData handler for the OSSS 'posts' data service.
    """

    mode = "posts"
    keywords = [
        "posts",
        "post list",
        "dcg posts",
        "osss posts",
        "district posts",
        "blog posts",
        "news posts",
    ]
    source_label = "DCG OSSS data service (posts)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "PostsHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )

        rows = await _fetch_posts(skip=skip, limit=limit)

        result: FetchResult = {
            "rows": rows,
            "posts": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }
        return result

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_posts_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_posts_csv(rows)


# register on import
register_handler(PostsHandler())
