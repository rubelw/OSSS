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

logger = logging.getLogger("OSSS.ai.agents.query_data.proposals")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE = os.getenv("OSSS_PROPOSALS_API_BASE", "http://host.containers.internal:8081")
PROPOSALS_ENDPOINT = "/api/proposals"

# How many rows we’re willing to render directly into markdown/CSV.
MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


# ---------------------------------------------------------------------------
# Low-level API client
# ---------------------------------------------------------------------------

async def _fetch_proposals(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Call the proposals API and return a list of proposal dicts.

    Raises:
        QueryDataError: if the HTTP call fails or the payload is unexpected.
    """
    url = f"{API_BASE}{PROPOSALS_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching proposals from %s with params skip=%s, limit=%s",
        url,
        skip,
        limit,
    )

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            verify=False,  # NOTE: intentional for internal dev; tighten in prod
        ) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            try:
                data = resp.json()
            except ValueError as json_err:
                logger.exception("Failed to decode proposals API JSON")
                raise QueryDataError(
                    f"Error decoding proposals API JSON: {json_err}",
                    proposals_url=url,
                ) from json_err

    except httpx.RequestError as e:
        logger.exception("Network error calling proposals API")
        raise QueryDataError(
            f"Network error querying proposals API: {e}",
            proposals_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        logger.exception(
            "Non-2xx status from proposals API: %s",
            getattr(e.response, "status_code", "unknown"),
        )
        status = getattr(e.response, "status_code", None)
        raise QueryDataError(
            f"Proposals API returned HTTP {status}",
            proposals_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling proposals API")
        raise QueryDataError(
            f"Unexpected error querying proposals API: {e}",
            proposals_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected proposals payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected proposals payload type: {type(data)!r}",
            proposals_url=url,
        )

    # Ensure all items are dicts (defensive)
    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in proposals payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug("Fetched %d proposals records (skip=%s, limit=%s)", len(cleaned), skip, limit)
    return cleaned


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------

def _escape_markdown_cell(value: Any) -> str:
    """
    Escape characters that break Markdown tables (e.g., pipes).
    """
    text = "" if value is None else str(value)
    # Escape pipes and backticks at minimum; you can extend this as needed.
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_fieldnames(rows: Sequence[Dict[str, Any]]) -> List[str]:
    """
    Derive a stable field order. Prefer common keys if present, then append the rest.
    """
    if not rows:
        return []

    # Common "nice" columns first if they exist
    preferred_order = [
        "id",
        "external_id",
        "name",
        "title",
        "status",
        "owner",
        "created_at",
        "updated_at",
    ]

    all_keys = list(rows[0].keys())
    for r in rows[1:]:
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


def _build_proposals_markdown_table(rows: List[Dict[str, Any]]) -> str:
    """
    Convert proposal rows to a Markdown table.

    If there are many rows, truncate to MAX_MARKDOWN_ROWS and note that truncation.
    """
    if not rows:
        return "No proposals records were found in the system."

    total_rows = len(rows)
    display_rows = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_fieldnames(display_rows)
    if not fieldnames:
        return "No proposals records were found in the system."

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
            f"_Showing first {MAX_MARKDOWN_ROWS} of {total_rows} proposals. "
            "You can ask for CSV to see the full dataset._"
        )

    return table


def _build_proposals_csv(rows: List[Dict[str, Any]]) -> str:
    """
    Convert proposal rows to CSV.

    If there are many rows, truncate to MAX_CSV_ROWS to keep payloads manageable.
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
        # Append a comment-ish footer; many CSV consumers will ignore this,
        # but it’s still human-visible if opened in a text editor.
        csv_text += f"# Truncated to first {MAX_CSV_ROWS} of {total_rows} proposals\n"

    return csv_text


# ---------------------------------------------------------------------------
# Query handler
# ---------------------------------------------------------------------------

class ProposalsHandler(QueryHandler):
    """
    QueryData handler for the OSSS "proposals" data service.
    """

    mode = "proposals"
    keywords = [
        "proposals",
        "proposal",
        "grant proposals",
        "DCG proposals",
        "OSSS proposals",
    ]
    source_label = "DCG OSSS data service (proposals)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        """
        Fetch proposals rows from the backing API.

        Returns a FetchResult mapping that includes:
          - 'rows': the primary row list
          - 'proposals': alias to the same rows for agent-specific use
        """
        logger.debug(
            "ProposalsHandler.fetch called (skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )

        rows = await _fetch_proposals(skip=skip, limit=limit)

        result: FetchResult = {
            "rows": rows,
            "proposals": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }
        return result

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_proposals_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_proposals_csv(rows)


# register on import
register_handler(ProposalsHandler())
