# src/OSSS/schemas/fan_app_settings.py
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------- Shared ----------
class FanAppSettingBase(BaseModel):
    """Fields common to create/update and read forms (excluding ids/timestamps)."""

    theme: dict[str, Any] | None = Field(
        default=None,
        description="Optional theme configuration (stored as JSON).",
    )
    features: dict[str, Any] | None = Field(
        default=None,
        description="Optional feature flags/configuration (stored as JSON).",
    )


# ---------- Create / Update ----------
class FanAppSettingCreate(FanAppSettingBase):
    """Payload to create a FanAppSetting."""
    school_id: UUID = Field(
        description="Owning School ID (unique constraint at the DB level)."
    )


class FanAppSettingUpdate(FanAppSettingBase):
    """Partial update; all fields optional."""
    school_id: UUID | None = Field(
        default=None,
        description="Owning School ID; may not be changed in all deployments.",
    )


# ---------- Read / Out ----------
class FanAppSettingOut(FanAppSettingBase):
    """Representation returned by the API."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    school_id: UUID
    created_at: datetime
    updated_at: datetime


# ---------- List wrapper ----------
class FanAppSettingList(BaseModel):
    """Standard list wrapper used by collection endpoints."""
    model_config = ConfigDict(from_attributes=True)

    total: int
    items: list[FanAppSettingOut]
