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

logger = logging.getLogger("OSSS.ai.agents.query_data.policy_legal_refs")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE = os.getenv(
    "OSSS_POLICY_LEGAL_REFS_API_BASE",
    "http://host.containers.internal:8081",
)
POLICY_LEGAL_REFS_ENDPOINT = "/api/policy_legal_refs"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


# ---------------------------------------------------------------------------
# Low-level API client
# ---------------------------------------------------------------------------

async def _fetch_policy_legal_refs(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Call the policy_legal_refs API and return a list of legal reference dicts.
    """
    url = f"{API_BASE}{POLICY_LEGAL_REFS_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching policy_legal_refs from %s with params skip=%s, limit=%s",
        url,
        skip,
        limit,
    )

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            verify=False,  # internal / dev; tighten in prod
        ) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            try:
                data = resp.json()
            except ValueError as json_err:
                logger.exception("Failed to decode policy_legal_refs API JSON")
                raise QueryDataError(
                    f"Error decoding policy_legal_refs API JSON: {json_err}",
                    policy_legal_refs_url=url,
                ) from json_err

    except httpx.RequestError as e:
        logger.exception("Network error calling policy_legal_refs API")
        raise QueryDataError(
            f"Network error querying policy_legal_refs API: {e}",
            policy_legal_refs_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("policy_legal_refs API returned HTTP %s", status)
        raise QueryDataError(
            f"policy_legal_refs API returned HTTP {status}",
            policy_legal_refs_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling policy_legal_refs API")
        raise QueryDataError(
            f"Unexpected error querying policy_legal_refs API: {e}",
            policy_legal_refs_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected policy_legal_refs payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected policy_legal_refs payload type: {type(data)!r}",
            policy_legal_refs_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in policy_legal_refs payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d policy_legal_refs records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------

def _escape_markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_fieldnames(rows: Sequence[Dict[str, Any]]) -> List[str]:
    if not rows:
        return []

    preferred_order = [
        "id",
        "policy_id",
        "policy_code",
        "legal_source",
        "citation",
        "reference_type",
        "jurisdiction",
        "notes",
        "status",
        "created_at",
        "updated_at",
    ]

    all_keys: List[str] = []
    for r in rows:
        for k in r.keys():
            if k not in all_keys:
                all_keys.append(k)

    ordered: List[str] = [k for k in preferred_order if k in all_keys]
    ordered.extend(k for k in all_keys if k not in ordered)
    return ordered


# ---------------------------------------------------------------------------
# Markdown + CSV
# ---------------------------------------------------------------------------

def _build_policy_legal_refs_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return "No policy_legal_refs records were found in the system."

    total_rows = len(rows)
    display_rows = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_fieldnames(display_rows)
    if not fieldnames:
        return "No policy_legal_refs records were found in the system."

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
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of {total_rows} policy legal reference records. "
            "You can request CSV to see the full dataset._"
        )

    return table


def _build_policy_legal_refs_csv(rows: List[Dict[str, Any]]) -> str:
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
            f"# Truncated to first {MAX_CSV_ROWS} of {total_rows} policy legal reference rows\n"
        )
    return csv_text


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

class PolicyLegalRefsHandler(QueryHandler):
    """
    QueryData handler for the OSSS 'policy_legal_refs' data service.
    """

    mode = "policy_legal_refs"
    keywords = [
        "policy legal refs",
        "policy legal references",
        "policy_legal_refs",
        "legal references for policies",
        "policy citations",
        "legal citations for policies",
        "dcg policy legal refs",
        "osss policy legal refs",
    ]
    source_label = "DCG OSSS data service (policy_legal_refs)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "PolicyLegalRefsHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )

        rows = await _fetch_policy_legal_refs(skip=skip, limit=limit)

        return {
            "rows": rows,
            "policy_legal_refs": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_policy_legal_refs_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_policy_legal_refs_csv(rows)


# register on import
register_handler(PolicyLegalRefsHandler())
