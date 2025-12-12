from __future__ import annotations

from typing import Optional
from pydantic.v1 import BaseModel, Field

from langchain_core.tools import StructuredTool

from OSSS.ai.langchain.agents.staff_info.staff_info_table import (
    run_staff_info_table_markdown_only,
)


# ------------------------------------------------------------------
# Tool input models (MUST be JSON-schema safe)
# ------------------------------------------------------------------

class StaffInfoFilters(BaseModel):
    school_id: Optional[str] = Field(default=None, description="Filter by school ID")
    active_only: Optional[bool] = Field(
        default=None, description="Only include active staff"
    )


class StaffInfoToolArgs(BaseModel):
    filters: Optional[StaffInfoFilters] = Field(
        default=None, description="Optional staff filters"
    )
    session_id: str = Field(default="", description="Session identifier")
    skip: int = Field(default=0, ge=0, description="Pagination offset")
    limit: int = Field(default=100, ge=1, le=500, description="Max rows to return")


# ------------------------------------------------------------------
# Tool builder
# ------------------------------------------------------------------

def build_staff_info_table_tool() -> StructuredTool:
    async def _run(
        *,
        filters: Optional[StaffInfoFilters] = None,
        session_id: str = "",
        skip: int = 0,
        limit: int = 100,
    ) -> str:
        return await run_staff_info_table_markdown_only(
            filters=filters,
            session_id=session_id,
            skip=skip,
            limit=limit,
        )

    return StructuredTool.from_function(
        coroutine=_run,
        name="staff_info_table",
        description=(
            "List staff directory records (teachers, administrators, etc.) "
            "from the OSSS backend. Supports optional filters and pagination."
        ),
        args_schema=StaffInfoToolArgs,  # ✅ THIS fixes your crash
    )
