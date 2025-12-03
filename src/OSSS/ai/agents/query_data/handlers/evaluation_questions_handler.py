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

logger = logging.getLogger("OSSS.ai.agents.query_data.evaluation_questions")

API_BASE = os.getenv(
    "OSSS_EVALUATION_QUESTIONS_API_BASE",
    "http://host.containers.internal:8081",
)
EVALUATION_QUESTIONS_ENDPOINT = "/api/evaluation_questions"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_evaluation_questions(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch evaluation_questions rows from the OSSS data API with robust error handling.
    """
    url = f"{API_BASE}{EVALUATION_QUESTIONS_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching evaluation_questions from %s with params skip=%s, limit=%s",
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
                logger.exception("Failed to decode evaluation_questions API JSON")
                raise QueryDataError(
                    f"Error decoding evaluation_questions API JSON: {json_err}",
                    evaluation_questions_url=url,
                ) from json_err

    except httpx.RequestError as e:
        logger.exception("Network error calling evaluation_questions API")
        raise QueryDataError(
            f"Network error querying evaluation_questions API: {e}",
            evaluation_questions_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("evaluation_questions API returned HTTP %s", status)
        raise QueryDataError(
            f"evaluation_questions API returned HTTP {status}",
            evaluation_questions_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling evaluation_questions API")
        raise QueryDataError(
            f"Unexpected error querying evaluation_questions API: {e}",
            evaluation_questions_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected evaluation_questions payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected evaluation_questions payload type: {type(data)!r}",
            evaluation_questions_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in evaluation_questions payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d evaluation_questions records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_evaluation_questions_fields(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    if not rows:
        return []

    preferred_order = [
        "id",
        "evaluation_template_id",
        "template_code",
        "evaluation_section_id",
        "section_code",
        "question_code",
        "question_text",
        "question_type",      # rating, rubric, comment, checkbox, etc.
        "response_scale",
        "min_score",
        "max_score",
        "weight",
        "sequence",
        "is_required",
        "is_active",
        "school_year",
        "created_at",
        "updated_at",
    ]

    all_keys: List[str] = []
    for r in rows:
        for k in r.keys():
            if k not in all_keys:
                all_keys.append(k)

    ordered = [k for k in preferred_order if k in all_keys]
    ordered.extend(k for k in all_keys if k not in ordered)
    return ordered


def _build_evaluation_questions_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return "No evaluation_questions records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_evaluation_questions_fields(display)
    if not fieldnames:
        return "No evaluation_questions records were found in the system."

    header_cells = ["#"] + fieldnames
    header = f"| {' | '.join(header_cells)} |\n"
    separator = f"| {' | '.join(['---'] * len(header_cells))} |\n"

    lines: List[str] = []
    for idx, r in enumerate(display, start=1):
        row_cells = [_escape_md(idx)] + [
            _escape_md(r.get(f, "")) for f in fieldnames
        ]
        lines.append(f"| {' | '.join(row_cells)} |")

    table = header + separator + "\n".join(lines)
    if total > MAX_MARKDOWN_ROWS:
        table += (
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of {total} evaluation question records. "
            "You can request CSV to see the full dataset._"
        )
    return table


def _build_evaluation_questions_csv(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]

    fieldnames = _select_evaluation_questions_fields(display)
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
            f"# Truncated to first {MAX_CSV_ROWS} of {total} evaluation_question rows\n"
        )
    return csv_text


class EvaluationQuestionsHandler(QueryHandler):
    mode = "evaluation_questions"
    keywords = [
        "evaluation questions",
        "evaluation_questions",
        "evaluation rubric questions",
        "observation questions",
        "teacher evaluation questions",
    ]
    source_label = "your DCG OSSS data service (evaluation_questions)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "EvaluationQuestionsHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )
        rows = await _fetch_evaluation_questions(skip=skip, limit=limit)
        return {
            "rows": rows,
            "evaluation_questions": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_evaluation_questions_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_evaluation_questions_csv(rows)


# register on import
register_handler(EvaluationQuestionsHandler())
