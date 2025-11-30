from __future__ import annotations

import csv
import io
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Live scoring formatting
# ---------------------------------------------------------------------------


def build_live_scorings_markdown_table(rows: List[Dict[str, Any]]) -> str:
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


def build_live_scorings_csv(rows: List[Dict[str, Any]]) -> str:
    """Return live scoring rows as CSV."""
    if not rows:
        return ""

    output = io.StringIO()
    fieldnames = ["game_id", "score", "status", "created_at", "updated_at", "id"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# ---------------------------------------------------------------------------
# Students / persons formatting
# ---------------------------------------------------------------------------


def build_student_markdown_table(rows: List[Dict[str, Any]]) -> str:
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


def build_student_csv(rows: List[Dict[str, Any]]) -> str:
    """Return CSV string containing all combined fields."""
    if not rows:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# ---------------------------------------------------------------------------
# Scorecards formatting
# ---------------------------------------------------------------------------


def build_scorecard_markdown_table(rows: List[Dict[str, Any]]) -> str:
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


def build_scorecard_csv(rows: List[Dict[str, Any]]) -> str:
    """Return CSV for scorecards."""
    if not rows:
        return ""

    output = io.StringIO()
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
