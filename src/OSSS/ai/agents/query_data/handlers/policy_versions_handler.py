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

logger = logging.getLogger("OSSS.ai.agents.query_data.policy_versions")

API_BASE = os.getenv(
    "OSSS_POLICY_VERSIONS_API_BASE",
    "http://host.containers.internal:8081",
)
POLICY_VERSIONS_ENDPOINT = "/api/policy_versions"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_policy_versions(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Call the policy_versions API and return a list of version dicts.
    """
    url = f"{API_BASE}{POLICY_VERSIONS_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching policy_versions from %s with params skip=%s, limit=%s",
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
                logger.exception("Failed to decode policy_versions API JSON")
                raise QueryDataError(
                    f"Error decoding policy_versions API JSON: {json_err}",
                    policy_versions_url=url,
                ) from json_err

    except httpx.RequestError as e:
        logger.exception("Network error calling policy_versions API")
        raise QueryDataError(
            f"Network error querying policy_versions API: {e}",
            policy_versions_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("policy_versions API returned HTTP %s", status)
        raise QueryDataError(
            f"policy_versions API returned HTTP {status}",
            policy_versions_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling policy_versions API")
        raise QueryDataError(
            f"Unexpected error querying policy_versions API: {e}",
            policy_versions_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected policy_versions payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected policy_versions payload type: {type(data)!r}",
            policy_versions_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in policy_versions payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d policy_versions records (skip=%s, limit=%s)",
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
        "policy_id",
        "policy_code",
        "version_number",
        "version_label",
        "status",
        "is_current",
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


def _build_policy_versions_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return "No policy_versions records were found in the system."

    total_rows = len(rows)
    display_rows = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_fieldnames(display_rows)
    if not fieldnames:
        return "No policy_versions records were found in the system."

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    lines: List[str] = []
    for idx, r in enumerate(display_rows, start=1):
        row_cells = [_escape_md(idx)] + [_escape_md(r.get(f, "")) for f in fieldnames]
        lines.append("| " + " | ".join(row_cells) + " |")

    table = header + separator + "\n".join(lines)

    if total_rows > MAX_MARKDOWN_ROWS:
        table += (
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of {total_rows} policy version records. "
            "You can request CSV to see the full dataset._"
        )

    return table


def _build_policy_versions_csv(rows: List[Dict[str, Any]]) -> str:
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
            f"# Truncated to first {MAX_CSV_ROWS} of {total_rows} policy version rows\n"
        )
    return csv_text


class PolicyVersionsHandler(QueryHandler):
    """
    QueryData handler for the OSSS 'policy_versions' data service.
    """

    mode = "policy_versions"
    keywords = [
        "policy versions",
        "policy_versions",
        "versions of policies",
        "policy version history",
        "dcg policy versions",
        "osss policy versions",
    ]
    source_label = "DCG OSSS data service (policy_versions)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "PolicyVersionsHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )

        rows = await _fetch_policy_versions(skip=skip, limit=limit)

        return {
            "rows": rows,
            "policy_versions": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_policy_versions_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_policy_versions_csv(rows)


register_handler(PolicyVersionsHandler())
