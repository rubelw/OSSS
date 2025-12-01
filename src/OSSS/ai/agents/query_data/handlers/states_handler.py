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
from OSSS.ai.agents.query_data.query_data_errors import QueryDataError

logger = logging.getLogger("OSSS.ai.agents.query_data.states")

API_BASE = "http://host.containers.internal:8081"

# Safety cap for markdown output
SAFE_MAX_ROWS = 200


# -------------------------------------------------------------------
# API Fetch
# -------------------------------------------------------------------
async def _fetch_states(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/states"
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
        logger.exception("HTTP error calling states API")
        raise QueryDataError(
            f"HTTP {status} error querying states API: {str(e)}",
            states_url=url,
        ) from e

    except Exception as e:
        logger.exception("Error calling states API")
        raise QueryDataError(
            f"Error querying states API: {str(e)}",
            states_url=url,
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected states payload type: {type(data)!r}",
            states_url=url,
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


def _extract_starts_with_letter(ctx: AgentContext) -> Optional[str]:
    """
    Look at the raw user text in the AgentContext and try to extract a
    leading-letter filter, e.g.:

      "list states beginning with I"
      "show us states that start with t"
      "states starting with 'M'"

    Returns an upper-case single letter or None.
    """
    # Try the obvious attributes; adjust if your AgentContext uses different names
    text = getattr(ctx, "query", None) or getattr(ctx, "raw_input", None)
    if not isinstance(text, str):
        return None

    lowered = text.lower()

    # Regex: "begin(s) with X", "starting with X", "start with X"
    # We capture a single letter after optional quotes.
    m = re.search(
        r"(begin(?:ning)?s?|starting|start)\s+with\s+['\"]?([a-z])",
        lowered,
    )
    if not m:
        return None

    letter = m.group(2)
    if not letter or len(letter) != 1:
        return None

    return letter.upper()


def _filter_states_by_prefix(
    rows: List[Dict[str, Any]],
    letter: str,
) -> List[Dict[str, Any]]:
    """
    Filter rows to those whose code/abbreviation OR name starts with `letter`.
    """
    if not letter or len(letter) != 1:
        return rows

    filtered: List[Dict[str, Any]] = []
    for r in rows:
        code = (
            r.get("code")
            or r.get("abbreviation")
            or r.get("state_code")
            or ""
        )
        name = r.get("name") or r.get("state_name") or ""

        code_str = str(code)
        name_str = str(name)

        if code_str.upper().startswith(letter) or name_str.upper().startswith(letter):
            filtered.append(r)

    logger.info(
        "[states] prefix filter=%r matched %d of %d rows",
        letter,
        len(filtered),
        len(rows),
    )
    return filtered or rows  # if nothing matched, fall back to full list


# -------------------------------------------------------------------
# Markdown Builder
# -------------------------------------------------------------------
def _build_states_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No states records were found in the system."

    # Enforce safety limit
    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No states records were found in the system."

    # Put id last if present
    if "id" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "id"] + ["id"]

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    body_lines: List[str] = []
    for idx, rec in enumerate(rows, start=1):
        row_cells: List[str] = [_stringify_cell(idx)]
        row_cells.extend(_stringify_cell(rec.get(f, "")) for f in fieldnames)
        body_lines.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(body_lines)


# -------------------------------------------------------------------
# CSV Builder
# -------------------------------------------------------------------
def _build_states_csv(rows: List[Dict[str, Any]]) -> str:
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
class StatesHandler(QueryHandler):
    mode = "states"
    keywords = [
        "states",
        "state list",
        "list of states",
        "us states",
        "state codes",
        "state abbreviations",
        "show states",
        "show state list",
    ]
    source_label = "your DCG OSSS data service (states)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        rows = await _fetch_states(skip=skip, limit=limit)

        # Optional: support "states beginning with I" style filters
        letter = _extract_starts_with_letter(ctx)
        if letter:
            logger.info("[states] applying starts-with letter filter: %s", letter)
            rows = _filter_states_by_prefix(rows, letter)

        return {"rows": rows, "states": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_states_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_states_csv(rows)


# register on import
register_handler(StatesHandler())
