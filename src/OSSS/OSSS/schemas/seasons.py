"""
Pydantic schemas for Season

Follows the same style/pattern as other schemas in `src/OSSS/schemas`.
Backed by model defined in `db/models/seasons.py`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# ---- Base ----
class SeasonBase(BaseModel):
    """Shared fields between create/read/update for a Season."""

    name: str = Field(..., max_length=64, description='Season label, e.g. "2025-2026"')
    start_year: int = Field(..., ge=0, description="Starting calendar year of the season")
    end_year: int = Field(..., ge=0, description="Ending calendar year of the season")

    @model_validator(mode="after")
    def _check_year_range(self):  # type: ignore[override]
        if self.end_year < self.start_year:
            raise ValueError("end_year must be greater than or equal to start_year")
        return self


# ---- Create ----
class SeasonCreate(SeasonBase):
    """Payload for creating a new Season."""

    pass


# ---- Update (PATCH) ----
class SeasonUpdate(BaseModel):
    """Partial update for an existing Season."""

    name: Optional[str] = Field(default=None, max_length=64)
    start_year: Optional[int] = Field(default=None, ge=0)
    end_year: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _validate_when_both_present(self):  # type: ignore[override]
        # Only validate relative order if both are provided in the PATCH
        if self.start_year is not None and self.end_year is not None:
            if self.end_year < self.start_year:
                raise ValueError("end_year must be greater than or equal to start_year")
        return self


# ---- Read ----
class SeasonRead(SeasonBase):
    """Replica of a persisted Season (as returned by the API)."""

    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Pydantic v2: allow construction from ORM objects
    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


# ---- Lightweight summaries / lists ----
class SeasonSummary(BaseModel):
    """Minimal listing view of seasons for tables or dropdowns."""

    id: UUID
    name: str
    start_year: int
    end_year: int

    model_config = {"from_attributes": True}


class SeasonList(BaseModel):
    """Container useful for list endpoints that wrap results (kept optional)."""

    items: list[SeasonSummary]
    total: int = Field(description="Total matching records (for pagination).")
