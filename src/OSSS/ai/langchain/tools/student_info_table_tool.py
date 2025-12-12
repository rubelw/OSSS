# src/OSSS/ai/langchain/tools/student_info_table_tool.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
import json
import logging
import ast

from pydantic import BaseModel, field_validator
from langchain_core.tools import StructuredTool

from OSSS.ai.langchain.agents.student_info_table import (
    StudentInfoFilters,
    run_student_info_table_markdown_only,
)

logger = logging.getLogger("OSSS.ai.langchain.student_info_table_tool")


# ---------------------------------------------------------------------------
# INPUT MODEL
# ---------------------------------------------------------------------------
class StudentInfoToolInput(BaseModel):
    first_name_prefix: Optional[str] = None
    last_name_prefix: Optional[str] = None
    genders: Optional[List[str]] = None
    grade_levels: Optional[List[str]] = None

    # NEW: allow filtering by enrollment status
    # - True  => only currently enrolled
    # - False => only withdrawn / inactive
    # - None  => no filter (current behavior)
    enrolled_only: Optional[bool] = None

    session_id: Optional[str] = None

    @field_validator("genders", "grade_levels", mode="before")
    @classmethod
    def _normalize_listish(cls, v: Any):
        """
        Accepts:
          - list[str]
          - '["FEMALE"]'      (JSON list)
          - "['FEMALE']"      (Python literal list)
          - 'FEMALE'
          - 'FEMALE,MALE'
        and returns list[str] or None.
        """
        if v is None:
            return None

        if isinstance(v, list):
            return [str(x) for x in v]

        if isinstance(v, str):
            s = v.strip()

            # Case 1: looks like a list
            if s.startswith("[") and s.endswith("]"):
                # Try JSON: '["FEMALE"]'
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        return [str(item) for item in parsed]
                except Exception:
                    logger.debug("Failed to json.loads(%r)", s)

                # Fallback: Python-list style "['FEMALE']"
                try:
                    parsed = ast.literal_eval(s)
                    if isinstance(parsed, list):
                        return [str(item) for item in parsed]
                except Exception:
                    logger.debug("Failed to ast.literal_eval(%r)", s)

                # if both fail, we fall through to treat as single value

            # Case 2: comma-separated
            if "," in s:
                return [p.strip() for p in s.split(",") if p.strip()]

            # Case 3: single value
            return [s]

        return v


# ---------------------------------------------------------------------------
# ASYNC TOOL IMPLEMENTATION
# ---------------------------------------------------------------------------
async def _student_info_table_tool_impl(
    first_name_prefix: str | None = None,
    last_name_prefix: str | None = None,
    genders: List[str] | None = None,
    grade_levels: List[str] | None = None,
    enrolled_only: bool | None = None,  # NEW
    session_id: str | None = None,
) -> str:
    logger.info(
        "[student_info_table_tool_impl] normalized args: "
        "first=%r last=%r genders=%r grades=%r enrolled_only=%r",
        first_name_prefix,
        last_name_prefix,
        genders,
        grade_levels,
        enrolled_only,
    )

    filters = StudentInfoFilters(
        first_name_prefix=first_name_prefix,
        last_name_prefix=last_name_prefix,
        genders=genders,
        grade_levels=grade_levels,
        enrolled_only=enrolled_only,  # NEW
    )

    # Returns a markdown string
    return await run_student_info_table_markdown_only(
        filters=filters,
        session_id=session_id or "student_info_table-session",
        skip=0,
        limit=100,
    )


# ---------------------------------------------------------------------------
# STRUCTURED TOOL (IMPORTANT: use coroutine=...)
# ---------------------------------------------------------------------------
student_info_table_tool: StructuredTool = StructuredTool(
    name="student_info_table",
    description=(
        "Summarize students in the OSSS backend. "
        "You can optionally filter by first_name_prefix, last_name_prefix, "
        "genders (e.g. ['MALE','FEMALE']), grade_levels (e.g. ['THIRD']), "
        "and enrolled_only (True for enrolled-only, False for withdrawn-only)."
    ),
    args_schema=StudentInfoToolInput,
    func=lambda *args, **kwargs: "<student_info_table async tool>",  # rarely used
    coroutine=_student_info_table_tool_impl,  # 👈 this is what the async agent will await
    return_direct=True,
)
