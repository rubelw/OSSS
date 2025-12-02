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

logger = logging.getLogger("OSSS.ai.agents.query_data.proposal_documents")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE = os.getenv(
    "OSSS_PROPOSAL_DOCS_API_BASE",
    "http://host.containers.internal:8081",
)
PROPOSAL_DOCUMENTS_ENDPOINT = "/api/proposal_documents"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


# ---------------------------------------------------------------------------
# Low-level API client
# ---------------------------------------------------------------------------

async def _fetch_proposal_documents(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Call the proposal_documents API and return a list of document dicts.

    Raises:
        QueryDataError: if the HTTP call fails or the payload is unexpected.
    """
    url = f"{API_BASE}{PROPOSAL_DOCUMENTS_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching proposal_documents from %s with params skip=%s, limit=%s",
        url,
        skip,
        limit,
    )

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            verify=False,  # internal dev; tighten for prod
        ) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            try:
                data = resp.json()
            except ValueError as json_err:
                logger.exception("Failed to decode proposal_documents API JSON")
                raise QueryDataError(
                    f"Error decoding proposal_documents API JSON: {json_err}",
                    proposal_documents_url=url,
                ) from json_err

    except httpx.RequestError as e:
        logger.exception("Network error calling proposal_documents API")
        raise QueryDataError(
            f"Network error querying proposal_documents API: {e}",
            proposal_documents_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception(
            "proposal_documents API returned HTTP %s",
            status,
        )
        raise QueryDataError(
            f"proposal_documents API returned HTTP {status}",
            proposal_documents_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling proposal_documents API")
        raise QueryDataError(
            f"Unexpected error querying proposal_documents API: {e}",
            proposal_documents_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected proposal_documents payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected proposal_documents payload type: {type(data)!r}",
            proposal_documents_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in proposal_documents payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d proposal_documents records (skip=%s, limit=%s)",
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
    Derive a stable field order for proposal_documents.
    """
    if not rows:
        return []

    preferred_order = [
        "id",
        "proposal_id",
        "document_name",
        "document_type",
        "file_name",
        "status",
        "created_at",
        "updated_at",
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

def _build_proposal_documents_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    """
    Convert proposal_documents rows to a Markdown table.

    Truncates to MAX_MARKDOWN_ROWS and notes truncation if needed.
    """
    if not rows:
        return "No proposal_documents records were found in the system."

    total_rows = len(rows)
    display_rows = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_fieldnames(display_rows)
    if not fieldnames:
        return "No proposal_documents records were found in the system."

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
            f"_Showing first {MAX_MARKDOWN_ROWS} of {total_rows} proposal document "
            "records. You can request CSV to see the full dataset._"
        )

    return table


def _build_proposal_documents_csv(rows: List[Dict[str, Any]]) -> str:
    """
    Convert proposal_documents rows to CSV.

    Truncates to MAX_CSV_ROWS and appends a footer comment if truncated.
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
            f"# Truncated to first {MAX_CSV_ROWS} of {total_rows} proposal document rows\n"
        )

    return csv_text


# ---------------------------------------------------------------------------
# Query handler
# ---------------------------------------------------------------------------

class ProposalDocumentsHandler(QueryHandler):
    """
    QueryData handler for the OSSS 'proposal_documents' data service.
    """

    mode = "proposal_documents"
    keywords = [
        "proposal documents",
        "proposal document list",
        "documents for proposals",
        "dcg proposal documents",
        "osss proposal documents",
        "grant proposal documents",
        "attached proposal documents",
    ]
    source_label = "DCG OSSS data service (proposal_documents)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "ProposalDocumentsHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )

        rows = await _fetch_proposal_documents(skip=skip, limit=limit)

        result: FetchResult = {
            "rows": rows,
            "proposal_documents": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }
        return result

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_proposal_documents_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_proposal_documents_csv(rows)


# register on import
register_handler(ProposalDocumentsHandler())
