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

logger = logging.getLogger("OSSS.ai.agents.query_data.iep_plans")

API_BASE = os.getenv(
    "OSSS_IEP_PLANS_API_BASE",
    "http://host.containers.internal:8081",
)
IEP_PLANS_ENDPOINT = "/api/iep_plans"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_iep_plans(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    url = f"{API_BASE}{IEP_PLANS_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching iep_plans from %s with params skip=%s, limit=%s",
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
                logger.exception("Failed to decode iep_plans API JSON")
                raise QueryDataError(
                    f"Error decoding iep_plans API JSON: {json_err}",
                    iep_plans_url=url,
                ) from json_err
    except httpx.RequestError as e:
        logger.exception("Network error calling iep_plans API")
        raise QueryDataError(
            f"Network error querying iep_plans API: {e}",
            iep_plans_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("iep_plans API returned HTTP %s", status)
        raise QueryDataError(
            f"iep_plans API returned HTTP {status}",
            iep_plans_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling iep_plans API")
        raise QueryDataError(
            f"Unexpected error querying iep_plans API: {e}",
            iep_plans_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected iep_plans payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected iep_plans payload type: {type(data)!r}",
            iep_plans_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in iep_plans payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d iep_plans records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_iep_plans_fields(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    if not rows:
        return []

    preferred_order = [
        "id",
        "iep_code",
        "student_id",
        "student_code",
        "student_name",
        "case_manager_id",
        "case_manager_name",
        "status",
        "eligibility_category",
        "start_date",
        "end_date",
        "next_review_date",
        "grade_level",
        "school",
        "created_at",
        "updated_at",
    ]

    all_keys: List[str] = []
    for r in rows:
        for k in r.keys():
            if k not in all_keys:
                all_keys.append(k)

    ordered = [k for k in preferred_order if k in all_keys]
    ordered.extend(x for x in all_keys if x not in ordered)
    return ordered


def _build_iep_plans_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return "No iep_plans records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_iep_plans_fields(display)
    if not fieldnames:
        return "No iep_plans records were found in the system."

    header_cells = ["#"] + fieldnames
    header = f"| {' | '.join(header_cells)} |\n"
    separator = f"| {' | '.join(['---'] * len(header_cells))} |\n"

    lines: List[str] = []
    for idx, r in enumerate(display, start=1):
        cells = [_escape_md(idx)] + [
            _escape_md(r.get(f, "")) for f in fieldnames
        ]
        lines.append(f"| {' | '.join(cells)} |")

    table = header + separator + "\n".join(lines)
    if total > MAX_MARKDOWN_ROWS:
        table += (
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of "
            f"{total} IEP plan records. "
            "You can request CSV to see the full dataset._"
        )
    return table


def _build_iep_plans_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]

    fieldnames = _select_iep_plans_fields(display)
    if not fieldnames:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(
        output, fieldnames=fieldnames, extrasaction="ignore"
    )
    writer.writeheader()
    writer.writerows(display)

    csv_text = output.getvalue()
    if total > MAX_CSV_ROWS:
        csv_text += (
            f"# Truncated to first {MAX_CSV_ROWS} of {total} IEP plan rows\n"
        )
    return csv_text


class IepPlansHandler(QueryHandler):
    mode = "iep_plans"
    keywords = [
        "iep plans",
        "iep_plans",
        "IEP list",
        "student IEPs",
        "special education plans",
    ]
    source_label = "your DCG OSSS data service (iep_plans)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "IepPlansHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )
        rows = await _fetch_iep_plans(skip=skip, limit=limit)
        return {
            "rows": rows,
            "iep_plans": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_iep_plans_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_iep_plans_csv(rows)


register_handler(IepPlansHandler())
