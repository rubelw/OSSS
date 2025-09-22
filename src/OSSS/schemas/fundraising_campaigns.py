# src/OSSS/schemas/fundraising_campaigns.py
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


__all__ = [
    "FundraisingCampaignBase",
    "FundraisingCampaignCreate",
    "FundraisingCampaignUpdate",
    "FundraisingCampaignRead",
]


class FundraisingCampaignBase(BaseModel):
    """
    Shared fields for FundraisingCampaign.
    Mirrors OSSS.db.models.fundraising_campaigns.FundraisingCampaign.
    """
    school_id: UUID
    name: str | None = None
    description: str | None = None
    target_cents: int | None = Field(default=None, ge=0)
    starts_on: date | None = None
    ends_on: date | None = None


class FundraisingCampaignCreate(FundraisingCampaignBase):
    """
    Payload for creating a FundraisingCampaign.
    (All fields from Base; model allows nullable name/description/dates/target.)
    """
    pass


class FundraisingCampaignUpdate(BaseModel):
    """
    PATCH/PUT payload; all fields optional.
    """
    school_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    target_cents: int | None = Field(default=None, ge=0)
    starts_on: date | None = None
    ends_on: date | None = None


class FundraisingCampaignRead(FundraisingCampaignBase):
    """
    Response model for a FundraisingCampaign record.
    """
    id: UUID
    created_at: datetime
    updated_at: datetime

    # Pydantic v2: allow ORM instances
    model_config = ConfigDict(from_attributes=True)
