from __future__ import annotations

import logging
from typing import Any, Dict, List
import httpx
import csv
import io
import json

from OSSS.ai.agents import register_agent
from OSSS.ai.agents.base import AgentContext, AgentResult

logger = logging.getLogger("OSSS.ai.agents.query_data.agent")

API_BASE = "http://host.containers.internal:8081"


# ---------------------------------------------------------------------------
# Data / tool layer: pure functions over the external "tables" (APIs)
# ---------------------------------------------------------------------------


class QueryDataError(Exception):
    """Raised when querying one of the external APIs fails."""

    def __init__(
        self,
        message: str,
        *,
        students_url: str | None = None,
        persons_url: str | None = None,
        scorecards_url: str | None = None,
        live_scorings_url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.students_url = students_url
        self.persons_url = persons_url
        self.scorecards_url = scorecards_url
        self.live_scorings_url = live_scorings_url


# ---------- Students + Persons tools ----------


async def _fetch_students_and_persons(
    *, skip: int = 0, limit: int = 100
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Low-level tool: call the external students and persons APIs
    and return the raw JSON payloads.
    """
    students_url = f"{API_BASE}/api/students"
    persons_url = f"{API_BASE}/api/persons"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Fetch students
            students_resp = await client.get(students_url, params=params)
            students_resp.raise_for_status()
            students: List[Dict[str, Any]] = students_resp.json()

            # Fetch persons
            persons_resp = await client.get(persons_url, params=params)
            persons_resp.raise_for_status()
            persons: List[Dict[str, Any]] = persons_resp.json()

    except Exception as e:
        logger.exception("Error calling students/persons API")
        raise QueryDataError(
            f"Error querying students/persons API: {e}",
            students_url=students_url,
            persons_url=persons_url,
        ) from e

    return {"students": students, "persons": persons}


def _combine_students_and_persons(
    students: List[Dict[str, Any]],
    persons: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Pure function: combine students + persons into a unified row list.
    """
    # Index persons by id
    persons_by_id = {p["id"]: p for p in persons if "id" in p}

    combined_rows: List[Dict[str, Any]] = []
    for s in students:
        pid = s.get("person_id")
        if not pid:
            continue

        person = persons_by_id.get(pid)
        if not person:
            continue

        combined_rows.append(
            {
                # person fields
                "person_id": person.get("id"),
                "first_name": person.get("first_name"),
                "middle_name": person.get("middle_name"),
                "last_name": person.get("last_name"),
                "dob": person.get("dob"),
                "email": person.get("email"),
                "phone": person.get("phone"),
                "gender": person.get("gender"),
                "person_created_at": person.get("created_at"),
                "person_updated_at": person.get("updated_at"),
                # student fields
                "student_id": s.get("id"),
                "student_number": s.get("student_number"),
                "graduation_year": s.get("graduation_year"),
                "student_created_at": s.get("created_at"),
                "student_updated_at": s.get("updated_at"),
            }
        )

    return combined_rows


async def query_students_tool(
    *, skip: int = 0, limit: int = 100
) -> Dict[str, Any]:
    """
    High-level data/tool function for students/persons.

    Returns raw students, persons, and combined rows.
    """
    payload = await _fetch_students_and_persons(skip=skip, limit=limit)
    students = payload["students"]
    persons = payload["persons"]
    combined_rows = _combine_students_and_persons(students, persons)

    return {
        "students": students,
        "persons": persons,
        "combined_rows": combined_rows,
    }


# ---------- Scorecards tools ----------


async def _fetch_scorecards(
    *, skip: int = 0, limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Low-level tool: call the external scorecards API and return JSON payload.
    """
    scorecards_url = f"{API_BASE}/api/scorecards"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(scorecards_url, params=params)
            resp.raise_for_status()
            scorecards: List[Dict[str, Any]] = resp.json()
    except Exception as e:
        logger.exception("Error calling scorecards API")
        raise QueryDataError(
            f"Error querying scorecards API: {e}",
            scorecards_url=scorecards_url,
        ) from e

    return scorecards


async def query_scorecards_tool(
    *, skip: int = 0, limit: int = 100
) -> List[Dict[str, Any]]:
    """
    High-level data/tool function for scorecards.

    Returns raw scorecards list.
    """
    return await _fetch_scorecards(skip=skip, limit=limit)


# ---------- Live scoring tools ----------


async def _fetch_live_scorings(
    skip: int = 0, limit: int = 100
) -> List[Dict[str, Any]]:
    """Call the OSSS live_scorings endpoint."""
    url = f"{API_BASE}/api/live_scorings"
    params = {"skip": skip, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                raise QueryDataError(
                    f"Live scoring query failed with status={resp.status_code}",
                    live_scorings_url=url,
                )
            data = resp.json()
    except QueryDataError:
        # already wrapped
        raise
    except Exception as e:
        logger.exception("Error calling live_scorings API")
        raise QueryDataError(
            f"Error querying live_scorings API: {e}",
            live_scorings_url=url,
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected live_scorings payload type: {type(data)!r}",
            live_scorings_url=url,
        )
    return data


async def query_live_scorings_tool(
    skip: int = 0, limit: int = 100
) -> List[Dict[str, Any]]:
    """Tool-like wrapper for fetching live scoring rows."""
    return await _fetch_live_scorings(skip=skip, limit=limit)


# ---------------------------------------------------------------------------
# Formatting helpers (still "dumb" utilities, not agents)
# ---------------------------------------------------------------------------


def _build_live_scorings_markdown_table(rows: List[Dict[str, Any]]) -> str:
    """Return live scoring rows as a markdown table."""
    if not rows:
        return "No live scoring records were found in the system."

    header = (
        "| # | Game ID | Score | Status | Created At | Updated At | Live Scoring ID |\n"
        "|---|---------|-------|--------|------------|------------|-----------------|\n"
    )

    lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        lines.append(
            f"| {idx} | "
            f"{r.get('game_id', '')} | "
            f"{r.get('score', '')} | "
            f"{r.get('status', '')} | "
            f"{r.get('created_at', '')} | "
            f"{r.get('updated_at', '')} | "
            f"{r.get('id', '')} |"
        )

    return header + "\n".join(lines)


def _build_live_scorings_csv(rows: List[Dict[str, Any]]) -> str:
    """Return live scoring rows as CSV."""
    if not rows:
        return ""

    output = io.StringIO()
    fieldnames = ["game_id", "score", "status", "created_at", "updated_at", "id"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _build_student_markdown_table(rows: List[Dict[str, Any]]) -> str:
    """Return student/person combined rows as a markdown table."""
    if not rows:
        return "No students were found in the system."

    header = (
        "| # | First | Middle | Last | DOB | Email | Phone | Gender | "
        "Person ID | Created At | Updated At | "
        "Student ID | Student Number | Graduation Year |\n"
        "|---|-------|--------|------|-----|-------|-------|--------|"
        "-----------|-------------|-------------|"
        "------------|----------------|----------------|\n"
    )

    lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        lines.append(
            f"| {idx} | "
            f"{r.get('first_name', '')} | "
            f"{r.get('middle_name', '')} | "
            f"{r.get('last_name', '')} | "
            f"{r.get('dob', '')} | "
            f"{r.get('email', '')} | "
            f"{r.get('phone', '')} | "
            f"{r.get('gender', '')} | "
            f"{r.get('person_id', '')} | "
            f"{r.get('person_created_at', '')} | "
            f"{r.get('person_updated_at', '')} | "
            f"{r.get('student_id', '')} | "
            f"{r.get('student_number', '')} | "
            f"{r.get('graduation_year', '')} |"
        )

    return header + "\n".join(lines)


def _build_student_csv(rows: List[Dict[str, Any]]) -> str:
    """Return CSV string containing all combined fields."""
    if not rows:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _build_scorecard_markdown_table(rows: List[Dict[str, Any]]) -> str:
    """Return scorecards as a markdown table."""
    if not rows:
        return "No scorecards were found in the system."

    header = (
        "| # | Scorecard ID | Plan ID | Name | Created At | Updated At |\n"
        "|---|--------------|---------|------|------------|------------|\n"
    )

    lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        lines.append(
            f"| {idx} | "
            f"{r.get('id', '')} | "
            f"{r.get('plan_id', '')} | "
            f"{r.get('name', '')} | "
            f"{r.get('created_at', '')} | "
            f"{r.get('updated_at', '')} |"
        )

    return header + "\n".join(lines)


def _build_scorecard_csv(rows: List[Dict[str, Any]]) -> str:
    """Return CSV for scorecards."""
    if not rows:
        return ""

    output = io.StringIO()
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# ---------------------------------------------------------------------------
# Thin AI agent layer: chooses which tool to call
# ---------------------------------------------------------------------------

MODE_STUDENTS = "students"
MODE_PERSONS = "persons"
MODE_SCORECARDS = "scorecards"
MODE_LIVE_SCORINGS = "live_scorings"


class QueryDataAgentResult:
    """Simple AgentResult-like container used by QueryDataAgent."""

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


def _detect_mode_from_context(ctx: AgentContext) -> str:
    """Decide whether to query students/persons, scorecards, or live_scorings."""
    q = (ctx.query or "").lower()

    # 1) Try to read an explicit mode from the intent classifier metadata
    meta_mode: str | None = None
    raw = ctx.metadata.get("intent_raw_model_output") if ctx.metadata else None
    if isinstance(raw, str):
        try:
            obj = json.loads(raw)
            heuristic_rule = obj.get("heuristic_rule") or {}
            metadata = heuristic_rule.get("metadata") or {}
            meta_mode = metadata.get("mode")
        except Exception:
            logger.exception(
                "QueryDataAgent: failed to parse intent_raw_model_output", exc_info=True
            )

    if meta_mode in {
        MODE_STUDENTS,
        MODE_PERSONS,
        MODE_SCORECARDS,
        MODE_LIVE_SCORINGS,
    }:
        logger.info("QueryDataAgent: using mode from classifier metadata: %s", meta_mode)
        return meta_mode

    # 2) Simple text heuristics as fallback
    if "scorecard" in q or "scorecards" in q:
        return MODE_SCORECARDS

    if (
        "live scoring" in q
        or "live score" in q
        or "live scores" in q
        or "live game" in q
    ):
        return MODE_LIVE_SCORINGS

    # Default: students/persons combined
    return MODE_STUDENTS


@register_agent("query_data")
class QueryDataAgent:
    async def run(self, ctx: AgentContext) -> AgentResult:
        skip = 0
        limit = 100

        mode = _detect_mode_from_context(ctx)
        logger.info("QueryDataAgent mode=%s", mode)

        try:
            if mode == MODE_SCORECARDS:
                scorecards = await query_scorecards_tool(skip=skip, limit=limit)
                table = _build_scorecard_markdown_table(scorecards)
                csv_data = _build_scorecard_csv(scorecards)

                answer = (
                    table
                    + "\n\n---\n\nThis data is coming from your DCG OSSS scorecards service."
                )
                agent_debug = {
                    "phase": "query_data",
                    "mode": mode,
                    "scorecard_count": len(scorecards),
                    "scorecards": scorecards,
                    "csv": csv_data,
                    "csv_filename": "scorecards_export.csv",
                }
                return QueryDataAgentResult(
                    status="ok",
                    answer_text=answer,
                    extra_chunks=[],
                    intent=ctx.intent or "query_data",
                    data={"agent_debug_information": agent_debug},
                    agent_id="query_data",
                    agent_name="QueryDataAgent",
                )

            elif mode == MODE_LIVE_SCORINGS:
                live_scorings = await query_live_scorings_tool(skip=skip, limit=limit)
                table = _build_live_scorings_markdown_table(live_scorings)
                csv_data = _build_live_scorings_csv(live_scorings)

                answer = (
                    table
                    + "\n\n---\n\nThis data is coming from your DCG OSSS live scoring service."
                )
                agent_debug = {
                    "phase": "query_data",
                    "mode": mode,
                    "live_scoring_count": len(live_scorings),
                    "live_scorings": live_scorings,
                    "csv": csv_data,
                    "csv_filename": "live_scorings_export.csv",
                }
                return QueryDataAgentResult(
                    status="ok",
                    answer_text=answer,
                    extra_chunks=[],
                    intent=ctx.intent or "query_data",
                    data={"agent_debug_information": agent_debug},
                    agent_id="query_data",
                    agent_name="QueryDataAgent",
                )

            else:
                # students/persons path
                data = await query_students_tool(skip=skip, limit=limit)
                students = data["students"]
                persons = data["persons"]
                combined = data["combined_rows"]

                table = _build_student_markdown_table(combined)
                csv_data = _build_student_csv(combined)

                answer = (
                    table
                    + "\n\n---\n\nThis data is coming from your DCG OSSS demo student/person service."
                )
                agent_debug = {
                    "phase": "query_data",
                    "mode": mode,
                    "student_count": len(students),
                    "person_count": len(persons),
                    "combined_count": len(combined),
                    "students": students,
                    "persons": persons,
                    "combined": combined,
                    "csv": csv_data,
                    "csv_filename": "students_export.csv",
                }
                return QueryDataAgentResult(
                    status="ok",
                    answer_text=answer,
                    extra_chunks=[],
                    intent=ctx.intent or "query_data",
                    data={"agent_debug_information": agent_debug},
                    agent_id="query_data",
                    agent_name="QueryDataAgent",
                )

        except QueryDataError as e:
            logger.exception("query_data_tool failed")
            # Build a generic error message but include whichever URLs we know
            lines = [
                "I attempted to query the backend APIs but encountered an error.",
                "",
            ]
            if e.students_url:
                lines.append(f"Students URL: {e.students_url}")
            if e.persons_url:
                lines.append(f"Persons URL: {e.persons_url}")
            if e.scorecards_url:
                lines.append(f"Scorecards URL: {e.scorecards_url}")
            if e.live_scorings_url:
                lines.append(f"Live scoring URL: {e.live_scorings_url}")

            return AgentResult(
                answer_text="\n".join(lines),
                status="error",
                intent="query_data",
                agent_id="query_data",
                agent_name="QueryDataAgent",
                data={
                    "agent_debug_information": {
                        "phase": "query_data",
                        "error": str(e),
                        "students_url": e.students_url,
                        "persons_url": e.persons_url,
                        "scorecards_url": e.scorecards_url,
                        "live_scorings_url": e.live_scorings_url,
                        "mode": mode,
                    }
                },
            )
