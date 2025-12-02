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
from OSSS.ai.agents.query_data.query_data_errors import QueryDataError

logger = logging.getLogger("OSSS.ai.agents.query_data.objectives")

API_BASE = os.getenv(
    "OSSS_OBJECTIVES_API_BASE",
    "http://host.containers.internal:8081",
)
OBJECTIVES_ENDPOINT = "/api/objectives"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_objectives(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    url = f"{API_BASE}{OBJECTIVES_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching objectives from %s with params skip=%s, limit=%s",
        url,
        skip,
        limit,
    )

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0), verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            try:
                data = resp.json()
            except ValueError as json_err:
                logger.exception("Failed to decode objectives API JSON")
                raise QueryDataError(
                    f"Error decoding objectives API JSON: {json_err}",
                    objectives_url=url,
                ) from json_err
    except httpx.RequestError as e:
        logger.exception("Network error calling objectives API")
        raise QueryDataError(
            f"Network error querying objectives API: {e}",
            objectives_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("objectives API returned HTTP %s", status)
        raise QueryDataError(
            f"objectives API returned HTTP {status}",
            objectives_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling objectives API")
        raise QueryDataError(
            f"Unexpected error querying objectives API: {e}",
            objectives_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected objectives payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected objectives payload type: {type(data)!r}",
            objectives_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in objectives payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d objectives records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_objectives_fields(rows: Sequence[Dict[str, Any]]) -> List[str]:
    if not rows:
        return []

    preferred_order = [
        "id",
        "objective_code",
        "title",
        "description",
        "category",
        "owner_id",
        "owner_name",
        "status",
        "start_date",
        "due_date",
        "completed_at",
        "created_at",
        "updated_at",
    ]

    all_keys: List[str] = []
    for r in rows:
        for k in r.keys():
            if k not in all_keys:
                all_keys.append(k)

    ordered = [c for c in preferred_order if c in all_keys]
    ordered.extend(k for k in all_keys if k not in ordered)
    return ordered


def _build_objectives_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No objectives records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]
    fieldnames = _select_objectives_fields(display)
    if not fieldnames:
        return "No objectives records were found in the system."

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    lines: List[str] = []
    for idx, r in enumerate(display, start=1):
        cells = [_escape_md(idx)] + [_escape_md(r.get(f, "")) for f in fieldnames]
        lines.append("| " + " | ".join(cells) + " |")

    table = header + separator + "\n".join(lines)

    if total > MAX_MARKDOWN_ROWS:
        table += (
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of {total} objective records. "
            "You can request CSV to see the full dataset._"
        )
    return table


def _build_objectives_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]
    fieldnames = _select_objectives_fields(display)
    if not fieldnames:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(display)

    csv_text = output.getvalue()
    if total > MAX_CSV_ROWS:
        csv_text += f"# Truncated to first {MAX_CSV_ROWS} of {total} objective rows\n"
    return csv_text


class ObjectivesHandler(QueryHandler):
    """
    QueryData handler for the OSSS 'objectives' data service.
    """

    mode = "objectives"
    keywords = [
        "objectives",
        "goals",
        "strategic objectives",
        "improvement objectives",
        "district goals",
        "osss objectives",
    ]
    source_label = "DCG OSSS data service (objectives)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "ObjectivesHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )
        rows = await _fetch_objectives(skip=skip, limit=limit)
        return {
            "rows": rows,
            "objectives": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_objectives_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_objectives_csv(rows)


register_handler(ObjectivesHandler())
