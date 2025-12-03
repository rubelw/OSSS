from __future__ import annotations

from typing import Any, Dict, List, Sequence
import csv
import httpx
import io
import logging
import os

from OSSS.ai.agents.base import AgentContext
from OSSS.ai.agents.query_data.query_data_registry import (
    FetchResult,
    QueryHandler,
    register_handler,
)
from OSSS.ai.agents.query_data.query_data_errors import QueryDataError

logger = logging.getLogger("OSSS.ai.agents.query_data.documents")

API_BASE = os.getenv(
    "OSSS_DOCUMENTS_API_BASE",
    "http://host.containers.internal:8081",
)
DOCUMENTS_ENDPOINT = "/api/documents"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_documents(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch documents rows from the OSSS data API with robust error handling.
    """
    url = f"{API_BASE}{DOCUMENTS_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching documents from %s with params skip=%s, limit=%s",
        url,
        skip,
        limit,
    )

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            verify=False,  # internal network; TLS handled elsewhere
        ) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            try:
                data = resp.json()
            except ValueError as json_err:
                logger.exception("Failed to decode documents API JSON")
                raise QueryDataError(
                    f"Error decoding documents API JSON: {json_err}",
                    documents_url=url,
                ) from json_err

    except httpx.RequestError as e:
        logger.exception("Network error calling documents API")
        raise QueryDataError(
            f"Network error querying documents API: {e}",
            documents_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("documents API returned HTTP %s", status)
        raise QueryDataError(
            f"documents API returned HTTP {status}",
            documents_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling documents API")
        raise QueryDataError(
            f"Unexpected error querying documents API: {e}",
            documents_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected documents payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected documents payload type: {type(data)!r}",
            documents_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in documents payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d documents records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    """
    Escape markdown-unfriendly characters for safe table rendering.
    """
    text = "" if value is None else str(value)
    return text.replace("|", r"\\|").replace("`", r"\\`")


def _select_documents_fields(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    """
    Choose a stable, user-friendly column ordering, but gracefully
    include any extra keys that the API returns.
    """
    if not rows:
        return []

    preferred_order = [
        "id",
        "folder_id",
        "folder_path",
        "title",
        "slug",
        "description",
        "document_type",      # policy, handbook, agenda, minutes, etc.
        "status",             # draft, published, archived
        "owner_id",
        "owner_name",
        "school_id",
        "school_name",
        "school_year",
        "tags",
        "version_id",
        "current_version_number",
        "published_at",
        "created_at",
        "updated_at",
        "source_system",
        "external_ref",
    ]

    all_keys: List[str] = []
    for r in rows:
        for k in r.keys():
            if k not in all_keys:
                all_keys.append(k)

    ordered = [k for k in preferred_order if k in all_keys]
    ordered.extend(k for k in all_keys if k not in ordered)
    return ordered


def _build_documents_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    """
    Render documents rows as a markdown table with row limits
    and a friendly truncation notice.
    """
    if not rows:
        return "No documents records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_documents_fields(display)
    if not fieldnames:
        return "No documents records were found in the system."

    header_cells = ["#"] + fieldnames
    header = f"| {' | '.join(header_cells)} |\n"
    separator = f"| {' | '.join(['---'] * len(header_cells))} |\n"

    lines: List[str] = []
    for idx, r in enumerate(display, start=1):
        row_cells = [_escape_md(idx)] + [
            _escape_md(r.get(f, "")) for f in fieldnames
        ]
        lines.append(f"| {' | '.join(row_cells)} |")

    table = header + separator + "\n".join(lines)

    if total > MAX_MARKDOWN_ROWS:
        table += (
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of {total} document records. "
            "You can request CSV to see the full dataset._"
        )

    return table


def _build_documents_csv(
    rows: List[Dict[str, Any]],
) -> str:
    """
    Render documents rows as CSV with a cap and comment-based truncation notice.
    """
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]

    fieldnames = _select_documents_fields(display)
    if not fieldnames:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(display)

    csv_text = output.getvalue()

    if total > MAX_CSV_ROWS:
        csv_text += (
            f"# Truncated to first {MAX_CSV_ROWS} of {total} document rows\n"
        )

    return csv_text


class DocumentsHandler(QueryHandler):
    mode = "documents"
    keywords = [
        "documents",
        "dcg documents",
        "district documents",
        "school documents",
        "policy documents",
        "handbooks",
    ]
    source_label = "your DCG OSSS data service (documents)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        """
        Load documents data and attach some simple metadata for the agent layer.
        """
        logger.debug(
            "DocumentsHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )

        rows = await _fetch_documents(skip=skip, limit=limit)

        return {
            "rows": rows,
            "documents": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }

    def to_markdown(
        self,
        rows: List[Dict[str, Any]],
    ) -> str:
        return _build_documents_markdown_table(rows)

    def to_csv(
        self,
        rows: List[Dict[str, Any]],
    ) -> str:
        return _build_documents_csv(rows)


# register on import
register_handler(DocumentsHandler())
