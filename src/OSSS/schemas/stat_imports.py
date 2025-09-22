# minimal placeholder to keep module name; see full definitions in earlier files.
"""
Pydantic schemas for StatImport

Follows the same style/pattern as other schemas in `src/OSSS/schemas`.
Backed by model defined in `db/models/stat_imports.py`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---- Base ----
class StatImportBase(BaseModel):
    """Shared fields between create/read/update for a StatImport record."""

    game_id: Optional[UUID] = Field(
        default=None,
        description="FK to the associated game (nullable).",
    )
    source_system: str = Field(
        ..., description="Source/system of the import (e.g., 'hudl', 'dragonfly')."
    )
    imported_at: Optional[datetime] = Field(
        default=None,
        description="When the stats were imported (UTC). If omitted on create, backend defaults.",
    )
    file_uri: Optional[str] = Field(
        default=None, description="URI or path of the imported file (if any)."
    )
    status: Optional[str] = Field(
        default=None,
        description="Status of the import, e.g., 'success' or 'failed' (optional).",
    )
    summary: Optional[dict] = Field(
        default=None,
        description="Optional JSON summary/metrics produced by the import pipeline.",
    )


# ---- Create ----
class StatImportCreate(BaseModel):
    """Payload for creating a new StatImport."""

    game_id: Optional[UUID] = Field(default=None, description="FK to the game (nullable).")
    source_system: str
    imported_at: Optional[datetime] = None
    file_uri: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[dict] = None


# ---- Update (PATCH) ----
class StatImportUpdate(BaseModel):
    """Partial update for an existing StatImport."""

    game_id: Optional[UUID] = None
    source_system: Optional[str] = None
    imported_at: Optional[datetime] = None
    file_uri: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[dict] = None


# ---- Read ----
class StatImportRead(StatImportBase):
    """Replica of a persisted StatImport (as returned by the API)."""

    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Pydantic v2: allow construction from ORM objects
    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


# ---- Lightweight summaries / lists ----
class StatImportSummary(BaseModel):
    """Minimal listing view of stat imports for tables or dropdowns."""

    id: UUID
    game_id: Optional[UUID] = None
    source_system: str
    imported_at: Optional[datetime] = None
    status: Optional[str] = None

    model_config = {"from_attributes": True}


class StatImportList(BaseModel):
    """Container useful for list endpoints that wrap results (kept optional)."""

    items: list[StatImportSummary]
    total: int = Field(description="Total matching records (for pagination).")
