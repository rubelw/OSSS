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

logger = logging.getLogger(
    "OSSS.ai.agents.query_data.data_sharing_agreements"
)

API_BASE = os.getenv(
    "OSSS_DATA_SHARING_AGREEMENTS_API_BASE",
    "http://host.containers.internal:8081",
)
DATA_SHARING_AGREEMENTS_ENDPOINT = "/api/data_sharing_agreements"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_data_sharing_agreements(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch data_sharing_agreements rows from the OSSS data API.
    """
    url = f"{API_BASE}{DATA_SHARING_AGREEMENTS_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching data_sharing_agreements from %s with params skip=%s, limit=%s",
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
                logger.exception(
                    "Failed to decode data_sharing_agreements API JSON"
                )
                raise QueryDataError(
                    "Error decoding data_sharing_agreements API JSON: "
                    f"{json_err}",
                    data_sharing_agreements_url=url,
                ) from json_err

    except httpx.RequestError as e:
        logger.exception("Network error calling data_sharing_agreements API")
        raise QueryDataError(
            f"Network error querying data_sharing_agreements API: {e}",
            data_sharing_agreements_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception(
            "data_sharing_agreements API returned HTTP %s",
            status,
        )
        raise QueryDataError(
            f"data_sharing_agreements API returned HTTP {status}",
            data_sharing_agreements_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling data_sharing_agreements API")
        raise QueryDataError(
            "Unexpected error querying data_sharing_agreements API: "
            f"{e}",
            data_sharing_agreements_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error(
            "Unexpected data_sharing_agreements payload type: %r",
            type(data),
        )
        raise QueryDataError(
            "Unexpected data_sharing_agreements payload type: "
            f"{type(data)!r}",
            data_sharing_agreements_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in "
                "data_sharing_agreements payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d data_sharing_agreements records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_data_sharing_agreements_fields(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    if not rows:
        return []

    preferred_order = [
        "id",
        "agreement_code",
        "name",
        "vendor_name",
        "vendor_product",
        "status",                  # active, pending, expired, archived
        "start_date",
        "end_date",
        "renewal_date",
        "jurisdiction",
        "data_categories",         # student, staff, both, etc.
        "contains_student_data",
        "contains_staff_data",
        "signed_date",
        "dpa_signed_date",
        "contract_url",
        "privacy_policy_url",
        "notes",
        "created_at",
        "updated_at",
    ]

    all_keys: List[str] = []
    for r in rows:
        for k in r.keys():
            if k not in all_keys:
                all_keys.append(k)

    ordered = [k for k in preferred_order if k in all_keys]
    ordered.extend([k for k in all_keys if k not in ordered])
    return ordered


def _build_data_sharing_agreements_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return "No data_sharing_agreements records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_data_sharing_agreements_fields(display)
    if not fieldnames:
        return "No data_sharing_agreements records were found in the system."

    header_cells = ["#"] + fieldnames
    header = f"| {' | '.join(header_cells)} |\n"
    separator = f"| {' | '.join(['---'] * len(header_cells))} |\n"
    lines: List[str] = []

    for idx, r in enumerate(display, start=1):
        row_cells = [_escape_md(idx)] + [_escape_md(r.get(f, "")) for f in fieldnames]
        lines.append(f"| {' | '.join(row_cells)} |")

    table = header + separator + "\n".join(lines)
    if total > MAX_MARKDOWN_ROWS:
        table += (
            "\n\n_Showing first "
            f"{MAX_MARKDOWN_ROWS} of {total} data sharing agreement records. "
            "You can request CSV to see the full dataset._"
        )

    return table


def _build_data_sharing_agreements_csv(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]

    fieldnames = _select_data_sharing_agreements_fields(display)
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
            "# Truncated to first "
            f"{MAX_CSV_ROWS} of {total} data_sharing_agreement rows\n"
        )

    return csv_text


class DataSharingAgreementsHandler(QueryHandler):
    mode = "data_sharing_agreements"
    keywords = [
        "data sharing agreements",
        "data_sharing_agreements",
        "vendor data agreements",
        "student data sharing agreements",
        "dpa agreements",
    ]
    source_label = "your DCG OSSS data service (data_sharing_agreements)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "DataSharingAgreementsHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )
        rows = await _fetch_data_sharing_agreements(skip=skip, limit=limit)
        return {
            "rows": rows,
            "data_sharing_agreements": rows,
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
        return _build_data_sharing_agreements_markdown_table(rows)

    def to_csv(
        self,
        rows: List[Dict[str, Any]],
    ) -> str:
        return _build_data_sharing_agreements_csv(rows)


# register on import
register_handler(DataSharingAgreementsHandler())
