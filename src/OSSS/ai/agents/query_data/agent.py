from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from OSSS.ai.agents import register_agent
from OSSS.ai.agents.base import AgentContext

from .tools import (
    StudentFilters,
    StudentRecord,
    get_student_tool,
    query_students_tool,
)

logger = logging.getLogger("OSSS.ai.agents.students.query")


# ---------------------------------------------------------------------------
# Result object expected by your router_agent
# ---------------------------------------------------------------------------

class QueryDataAgentResult:
    """
    Keep this simple: your router only cares that it can getattr() fields.
    """

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# Optional internal reasoning logging
# ---------------------------------------------------------------------------

@dataclass
class ReasoningStep:
    phase: str
    thought: str
    action: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

@register_agent(
    name="students.query",
    description=(
        "Lookup K-12 students in OSSS by name, grade, or ID. "
        "Uses the Student table and related enrollment records under the hood."
    ),
)
async def query_students_agent(
    ctx: AgentContext,
    query_text: Optional[str] = None,
    student_id: Optional[UUID] = None,
    external_id: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    grade_level: Optional[str] = None,
    active_only: bool = True,
    limit: int = 25,
) -> QueryDataAgentResult:
    """
    Thin AI agent wrapper around the data/tool layer.

    Responsibilities:
      - Interpret input / query_text
      - Build StudentFilters
      - Call query_students_tool() or get_student_tool()
      - Shape data into a router-friendly result
    """

    reasoning: List[ReasoningStep] = []

    reasoning.append(
        ReasoningStep(
            phase="input",
            thought="Received a student query request.",
            details={
                "query_text": query_text,
                "student_id": str(student_id) if student_id else None,
                "external_id": external_id,
                "first_name": first_name,
                "last_name": last_name,
                "grade_level": grade_level,
                "active_only": active_only,
                "limit": limit,
            },
        )
    )

    # -------------------------------------------------------------
    # 1. If a concrete student_id is provided, prefer direct lookup
    # -------------------------------------------------------------
    if student_id:
        reasoning.append(
            ReasoningStep(
                phase="plan",
                thought="Direct lookup by student_id.",
                action="get_student_tool",
                details={"student_id": str(student_id)},
            )
        )

        student = await get_student_tool(student_id)
        if not student:
            reasoning.append(
                ReasoningStep(
                    phase="result",
                    thought="No student found with that id.",
                    details={},
                )
            )
            return QueryDataAgentResult(
                success=False,
                message="No student found with that id.",
                students=[],
                reasoning=[asdict(r) for r in reasoning],
            )

        return QueryDataAgentResult(
            success=True,
            message="Found student by id.",
            students=[_student_to_dict(student)],
            reasoning=[asdict(r) for r in reasoning],
        )

    # -------------------------------------------------------------
    # 2. Build filters for a more general search
    # -------------------------------------------------------------
    reasoning.append(
        ReasoningStep(
            phase="plan",
            thought="Build filters from provided fields for general search.",
            action="query_students_tool",
        )
    )

    filters = StudentFilters(
        student_id=None,
        external_id=external_id,
        first_name=first_name,
        last_name=last_name,
        grade_level=grade_level,
        active_only=active_only,
        limit=limit,
    )

    students = await query_students_tool(filters)

    reasoning.append(
        ReasoningStep(
            phase="result",
            thought=f"Found {len(students)} matching students.",
            details={"count": len(students)},
        )
    )

    return QueryDataAgentResult(
        success=True,
        message=f"Found {len(students)} matching students.",
        students=[_student_to_dict(s) for s in students],
        reasoning=[asdict(r) for r in reasoning],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _student_to_dict(s: StudentRecord) -> Dict[str, Any]:
    """Shape student data for JSON / router_agent."""
    return {
        "id": str(s.id),
        "first_name": s.first_name,
        "last_name": s.last_name,
        "full_name": f"{s.first_name} {s.last_name}".strip(),
        "grade_level": s.grade_level,
        "external_id": s.external_id,
        "is_active": s.is_active,
    }
