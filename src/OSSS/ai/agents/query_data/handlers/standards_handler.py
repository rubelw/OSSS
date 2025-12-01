from __future__ import annotations

from typing import Any, Dict, List, Optional
import httpx
import csv
import io
import logging

from OSSS.ai.agents.base import AgentContext
from OSSS.ai.agents.query_data.query_data_registry import (
    QueryHandler,
    FetchResult,
    register_handler,
)
from OSSS.ai.agents.query_data.query_data_errors import QueryDataError  # optional

logger = logging.getLogger("OSSS.ai.agents.query_data.standards")

API_BASE = "http://host.containers.internal:8081"


# ---------------------------------------------------------------------------
# Low-level fetch helper
# ---------------------------------------------------------------------------

async def _fetch_standards(
    skip: int = 0,
    limit: int = 100,
    extra_params: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Call the /api/standards endpoint on the OSSS data service.

    extra_params can be used later for things like filtering or search
    (e.g. {"search": "math"}), but it’s optional and safe to omit.
    """
    url = f"{API_BASE}/api/standards"

    params: Dict[str, Any] = {"skip": skip, "limit": limit}
    if extra_params:
        # let caller override / extend query params
        params.update(extra_params)

    logger.info(
        "[standards] calling OSSS data service url=%s params=%s",
        url,
        params,
    )

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            logger.info(
                "[standards] response status=%s bytes=%s",
                resp.status_code,
                len(resp.content),
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.exception("Error calling standards API")
        raise QueryDataError(
            f"Error querying standards API: {e}",
            standards_url=url,
            standards_params=params,
        ) from e

    # Some backends return {"items":[...]} instead of just [...]
    if isinstance(data, dict) and "items" in data:
        data = data["items"]

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected standards payload type: {type(data)!r}",
            standards_url=url,
            standards_params=params,
        )

    logger.info("[standards] fetched %d rows", len(data))
    return data


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------

def _select_display_fields(rows: List[Dict[str, Any]]) -> List[str]:
    """
    Heuristic: for standards we typically care about codes and names first.
    Fall back to a small subset of columns if there are many.
    """
    if not rows:
        return []

    all_fields = list(rows[0].keys())

    preferred_order = [
        "id",
        "external_id",
        "standard_id",
        "code",
        "standard_code",
        "short_code",
        "name",
        "title",
        "subject",
        "grade_level",
        "grade_band",
        "created_at",
        "updated_at",
    ]
    chosen: List[str] = [f for f in preferred_order if f in all_fields]

    # if nothing matched, just show up to first 8 columns
    if not chosen:
        return all_fields[:8]

    # add a few extra fields to give context, but avoid blowing up the table
    extras = [f for f in all_fields if f not in chosen]
    chosen.extend(extras[:4])
    return chosen


def _build_standards_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No standards records were found in the system."

    fieldnames = _select_display_fields(rows)
    if not fieldnames:
        return "No standards records were found in the system."

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        row_cells = [str(idx)] + [str(r.get(f, "")) for f in fieldnames]
        lines.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(lines)


def _build_standards_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    fieldnames = _select_display_fields(rows)
    if not fieldnames:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for r in rows:
        writer.writerow({f: r.get(f, "") for f in fieldnames})

    return output.getvalue()


# ---------------------------------------------------------------------------
# QueryHandler implementation
# ---------------------------------------------------------------------------

class StandardsHandler(QueryHandler):
    """
    Query handler for the `standards` table.

    Mode: "standards"
    Typical usage: routed via the intent classifier when the user asks
    about academic/learning standards, codes, and descriptions.
    """

    mode = "standards"
    keywords = [
        "standards",
        "academic standards",
        "learning standards",
        "state standards",
        "standards codes",
    ]
    source_label = "your DCG OSSS data service (standards)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        """
        Fetch standards rows. In the future we can plumb simple filters
        from ctx into extra_params if we want (e.g., subject or grade).
        """
        extra_params: Dict[str, Any] = {}

        # Example hook: if your AgentContext carries a simple search term,
        # you could pass it through as ?q=... to the FastAPI layer.
        query_text = getattr(ctx, "query", None) or getattr(ctx, "raw_input", None)
        if isinstance(query_text, str) and query_text.strip():
            # FastAPI side would need to accept this (e.g. q: str | None = Query(None))
            extra_params["q"] = query_text.strip()

        rows = await _fetch_standards(skip=skip, limit=limit, extra_params=extra_params)
        return {
            "rows": rows,
            "standards": rows,
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_standards_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_standards_csv(rows)


# register on import
register_handler(StandardsHandler())
