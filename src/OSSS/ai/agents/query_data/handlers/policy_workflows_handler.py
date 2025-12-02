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

logger = logging.getLogger("OSSS.ai.agents.query_data.policy_workflows")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE = os.getenv(
    "OSSS_POLICY_WORKFLOWS_API_BASE",
    "http://host.containers.internal:8081",
)
POLICY_WORKFLOWS_ENDPOINT = "/api/policy_workflows"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


# ---------------------------------------------------------------------------
# Low-level API client
# ---------------------------------------------------------------------------

async def _fetch_policy_workflows(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Call the policy_workflows API and return a list of workflow dicts.

    Raises:
        QueryDataError: if the HTTP call fails or the payload is unexpected.
    """
    url = f"{API_BASE}{POLICY_WORKFLOWS_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching policy_workflows from %s with params skip=%s, limit=%s",
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
                logger.exception("Failed to decode policy_workflows API JSON")
                raise QueryDataError(
                    f"Error decoding policy_workflows API JSON: {json_err}",
                    policy_workflows_url=url,
                ) from json_err

    except httpx.RequestError as e:
        logger.exception("Network error calling policy_workflows API")
        raise QueryDataError(
            f"Network error querying policy_workflows API: {e}",
            policy_workflows_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("policy_workflows API returned HTTP %s", status)
        raise QueryDataError(
            f"policy_workflows API returned HTTP {status}",
            policy_workflows_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling policy_workflows API")
        raise QueryDataError(
            f"Unexpected error querying policy_workflows API: {e}",
            policy_workflows_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected policy_workflows payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected policy_workflows payload type: {type(data)!r}",
            policy_workflows_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in policy_workflows payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d policy_workflows records (skip=%s, limit=%s)",
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
    Derive a stable field order for policy_workflows.
    """
    if not rows:
        return []

    preferred_order = [
        "id",
        "policy_id",
        "policy_code",
        "workflow_name",
        "workflow_type",
        "step_name",
        "step_order",
        "current_step",
        "owner",
        "assignee",
        "status",
        "is_active",
        "started_at",
        "completed_at",
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

def _build_policy_workflows_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    """
    Convert policy_workflows rows to a Markdown table, truncating if needed.
    """
    if not rows:
        return "No policy_workflows records were found in the system."

    total_rows = len(rows)
    display_rows = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_fieldnames(display_rows)
    if not fieldnames:
        return "No policy_workflows records were found in the system."

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
            f"_Showing first {MAX_MARKDOWN_ROWS} of {total_rows} policy workflow records. "
            "You can request CSV to see the full dataset._"
        )

    return table


def _build_policy_workflows_csv(rows: List[Dict[str, Any]]) -> str:
    """
    Convert policy_workflows rows to CSV, truncating if needed.
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
            f"# Truncated to first {MAX_CSV_ROWS} of {total_rows} policy workflow rows\n"
        )

    return csv_text


# ---------------------------------------------------------------------------
# Query handler
# ---------------------------------------------------------------------------

class PolicyWorkflowsHandler(QueryHandler):
    """
    QueryData handler for the OSSS 'policy_workflows' data service.
    """

    mode = "policy_workflows"
    keywords = [
        "policy workflows",
        "policy_workflows",
        "policy approval workflows",
        "policy review workflows",
        "dcg policy workflows",
        "osss policy workflows",
    ]
    source_label = "DCG OSSS data service (policy_workflows)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "PolicyWorkflowsHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )

        rows = await _fetch_policy_workflows(skip=skip, limit=limit)

        result: FetchResult = {
            "rows": rows,
            "policy_workflows": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }
        return result

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_policy_workflows_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_policy_workflows_csv(rows)


# register on import
register_handler(PolicyWorkflowsHandler())
