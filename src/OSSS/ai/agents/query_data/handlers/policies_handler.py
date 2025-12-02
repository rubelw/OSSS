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

logger = logging.getLogger("OSSS.ai.agents.query_data.policies")

API_BASE = os.getenv(
    "OSSS_POLICIES_API_BASE",
    "http://host.containers.internal:8081",
)
POLICIES_ENDPOINT = "/api/policys"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_policies(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Call the policies API and return a list of policy dicts.
    """
    url = f"{API_BASE}{POLICIES_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching policies from %s with params skip=%s, limit=%s",
        url,
        skip,
        limit,
    )

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            verify=False,
        ) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            try:
                data = resp.json()
            except ValueError as json_err:
                logger.exception("Failed to decode policies API JSON")
                raise QueryDataError(
                    f"Error decoding policies API JSON: {json_err}",
                    policies_url=url,
                ) from json_err

    except httpx.RequestError as e:
        logger.exception("Network error calling policies API")
        raise QueryDataError(
            f"Network error querying policies API: {e}",
            policies_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("policies API returned HTTP %s", status)
        raise QueryDataError(
            f"policies API returned HTTP {status}",
            policies_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling policies API")
        raise QueryDataError(
            f"Unexpected error querying policies API: {e}",
            policies_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected policies payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected policies payload type: {type(data)!r}",
            policies_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in policies payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d policies records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_fieldnames(rows: Sequence[Dict[str, Any]]) -> List[str]:
    if not rows:
        return []

    preferred_order = [
        "id",
        "policy_code",
        "title",
        "short_title",
        "category",
        "subcategory",
        "status",
        "is_active",
        "owner",
        "department",
        "effective_date",
        "retired_date",
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


def _build_policies_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return "No policies records were found in the system."

    total_rows = len(rows)
    display_rows = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_fieldnames(display_rows)
    if not fieldnames:
        return "No policies records were found in the system."

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    lines: List[str] = []
    for idx, r in enumerate(display_rows, start=1):
        row_cells = [_escape_md(idx)] + [
            _escape_md(r.get(f, "")) for f in fieldnames
        ]
        lines.append("| " + " | ".join(row_cells) + " |")

    table = header + separator + "\n".join(lines)

    if total_rows > MAX_MARKDOWN_ROWS:
        table += (
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of {total_rows} policy records. "
            "You can request CSV to see the full dataset._"
        )

    return table


def _build_policies_csv(rows: List[Dict[str, Any]]) -> str:
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
            f"# Truncated to first {MAX_CSV_ROWS} of {total_rows} policy rows\n"
        )
    return csv_text


class PoliciesHandler(QueryHandler):
    """
    QueryData handler for the OSSS 'policies' data service.
    """

    mode = "policies"
    keywords = [
        "policies",
        "district policies",
        "board policies",
        "dcg policies",
        "osss policies",
        "policy list",
        "list of policies",
    ]
    source_label = "DCG OSSS data service (policies)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "PoliciesHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )

        rows = await _fetch_policies(skip=skip, limit=limit)

        return {
            "rows": rows,
            "policies": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_policies_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_policies_csv(rows)


# register on import
register_handler(PoliciesHandler())
