from __future__ import annotations

from typing import Any, Dict, List, Optional
import httpx
import csv
import io
import logging
import re

from OSSS.ai.agents.base import AgentContext
from OSSS.ai.agents.query_data.query_data_registry import (
    QueryHandler,
    FetchResult,
    register_handler,
)
from OSSS.ai.agents.query_data.query_data_errors import QueryDataError  # optional

logger = logging.getLogger("OSSS.ai.agents.query_data.standardized_tests")

API_BASE = "http://host.containers.internal:8081"

# Safety cap for markdown output
SAFE_MAX_ROWS = 200


# -------------------------------------------------------------------
# API Fetch
# -------------------------------------------------------------------
async def _fetch_standardized_tests(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/standardized_tests"
    params = {"skip": skip, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

    except httpx.HTTPStatusError as e:
        status = (
            e.response.status_code
            if getattr(e, "response", None) is not None
            else "unknown"
        )
        logger.exception("HTTP error calling standardized_tests API")
        raise QueryDataError(
            f"HTTP {status} error querying standardized_tests API: {str(e)}",
            standardized_tests_url=url,
        ) from e

    except Exception as e:
        logger.exception("Error calling standardized_tests API")
        raise QueryDataError(
            f"Error querying standardized_tests API: {str(e)}",
            standardized_tests_url=url,
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected standardized_tests payload type: {type(data)!r}",
            standardized_tests_url=url,
        )
    return data


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _stringify_cell(value: Any, max_len: int = 120) -> str:
    """Convert a value to a trimmed, safe string for markdown tables."""
    if value is None:
        return ""
    s = str(value)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


def _extract_test_keyword(ctx: AgentContext) -> Optional[str]:
    """
    Look at the raw user text and try to figure out if they're asking
    about a particular standardized test family, e.g.:

      - "ACT scores", "show ACT standardized tests"
      - "SAT results"
      - "Iowa Assessments"
      - "MAP testing", "NWEA MAP"
      - "FAST reading"

    Returns a canonical keyword (e.g. "ACT", "SAT", "IOWA", "MAP", "FAST")
    or None if nothing obvious is found.
    """
    text = getattr(ctx, "query", None) or getattr(ctx, "raw_input", None)
    if not isinstance(text, str):
        return None

    lowered = text.lower()

    # Simple keyword detection; extend as needed
    if " act " in f" {lowered} " or "act test" in lowered:
        return "ACT"
    if " sat " in f" {lowered} " or "sat test" in lowered:
        return "SAT"
    if "iowa assessment" in lowered or "iowa tests" in lowered:
        return "IOWA"
    if " map " in f" {lowered} " or "nwea" in lowered or "map testing" in lowered:
        return "MAP"
    if " fast " in f" {lowered} " or "fast assessment" in lowered:
        return "FAST"

    return None


def _filter_standardized_tests_by_keyword(
    rows: List[Dict[str, Any]],
    keyword: str,
) -> List[Dict[str, Any]]:
    """
    Filter standardized_tests rows by a detected keyword (ACT, SAT, MAP, etc).
    We look in common columns like name/test_name/code, falling back to a
    full-row string search.
    """
    if not keyword:
        return rows

    kw_lower = keyword.lower()
    filtered: List[Dict[str, Any]] = []

    for r in rows:
        name = r.get("name") or r.get("test_name") or ""
        code = r.get("code") or r.get("test_code") or ""

        name_str = str(name).lower()
        code_str = str(code).lower()

        # direct hits in name/code
        if kw_lower in name_str or kw_lower in code_str:
            filtered.append(r)
            continue

        # as a fallback, search the entire row string
        full_str = " ".join(str(v) for v in r.values()).lower()
        if kw_lower in full_str:
            filtered.append(r)

    logger.info(
        "[standardized_tests] keyword filter=%r matched %d of %d rows",
        keyword,
        len(filtered),
        len(rows),
    )
    return filtered or rows  # if no match, fall back to full list


# -------------------------------------------------------------------
# Markdown Builder
# -------------------------------------------------------------------
def _build_standardized_tests_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No standardized_tests records were found in the system."

    # Enforce safety limit
    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No standardized_tests records were found in the system."

    # Put id last if present (nice for readability)
    if "id" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "id"] + ["id"]

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    body_lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        row_cells: List[str] = [_stringify_cell(idx)]
        row_cells.extend(_stringify_cell(r.get(f, "")) for f in fieldnames)
        body_lines.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(body_lines)


# -------------------------------------------------------------------
# CSV Builder
# -------------------------------------------------------------------
def _build_standardized_tests_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    fieldnames = list(rows[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# -------------------------------------------------------------------
# Handler
# -------------------------------------------------------------------
class StandardizedTestsHandler(QueryHandler):
    mode = "standardized_tests"
    keywords = [
        "standardized_tests",
        "standardized tests",
        "ACT test",
        "SAT test",
        "Iowa Assessments",
        "MAP testing",
        "FAST assessment",
    ]
    source_label = "your DCG OSSS data service (standardized_tests)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        rows = await _fetch_standardized_tests(skip=skip, limit=limit)

        # Optional small UX boost: if the user named a specific test family,
        # narrow to that set of tests.
        keyword = _extract_test_keyword(ctx)
        if keyword:
            logger.info(
                "[standardized_tests] applying keyword filter based on user text: %s",
                keyword,
            )
            rows = _filter_standardized_tests_by_keyword(rows, keyword)

        return {"rows": rows, "standardized_tests": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_standardized_tests_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_standardized_tests_csv(rows)


# register on import
register_handler(StandardizedTestsHandler())
