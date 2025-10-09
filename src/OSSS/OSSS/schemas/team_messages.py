"""
Pydantic schemas for TeamMessage

Follows the same style/pattern as other schemas in `src/OSSS/schemas`.
Backed by model defined in `db/models/team_messages.py`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

# Keep enum aligned with the SQLAlchemy model
try:
    from OSSS.db.models.common_enums import MessageChannel  # type: ignore
except Exception:  # lightweight fallback for typing/runtime in isolation
    from enum import Enum

    class MessageChannel(str, Enum):  # type: ignore[no-redef]
        email = "email"
        sms = "sms"
        push = "push"
        inapp = "inapp"


# ---- Base ----
class TeamMessageBase(BaseModel):
    """Shared fields between create/read/update for a TeamMessage record."""

    channel: MessageChannel = Field(
        ..., description="Delivery channel, e.g., 'email', 'sms', 'push', 'inapp'."
    )
    subject: Optional[str] = Field(
        default=None, max_length=255, description="Optional subject/short title."
    )
    body: Optional[str] = Field(
        default=None, description="Optional message body (text/HTML allowed)."
    )
    sent_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp when the message was (to be) sent. Defaults server-side.",
    )
    status: Optional[str] = Field(
        default=None,
        max_length=32,
        description="Queue state like 'queued', 'sent', or 'failed'.",
    )


# ---- Create ----
class TeamMessageCreate(TeamMessageBase):
    """Payload for creating a new TeamMessage."""

    team_id: UUID = Field(description="FK to the associated team.")
    sender_id: Optional[UUID] = Field(
        default=None, description="User ID that initiated the message (nullable for system)."
    )


# ---- Update (PATCH) ----
class TeamMessageUpdate(BaseModel):
    """Partial update for an existing TeamMessage."""

    channel: Optional[MessageChannel] = None
    subject: Optional[str] = Field(default=None, max_length=255)
    body: Optional[str] = None
    sent_at: Optional[datetime] = None
    status: Optional[str] = Field(default=None, max_length=32)
    team_id: Optional[UUID] = None
    sender_id: Optional[UUID] = None


# ---- Read ----
class TeamMessageRead(TeamMessageBase):
    """Replica of a persisted TeamMessage (as returned by the API)."""

    id: UUID
    team_id: UUID
    sender_id: Optional[UUID] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Pydantic v2: allow construction from ORM objects
    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


# ---- Lightweight summaries / lists ----
class TeamMessageSummary(BaseModel):
    """Minimal listing view of team messages for tables or dropdowns."""

    id: UUID
    team_id: UUID
    channel: MessageChannel
    subject: Optional[str] = None
    sent_at: Optional[datetime] = None
    status: Optional[str] = None

    model_config = {"from_attributes": True}


class TeamMessageList(BaseModel):
    """Container useful for list endpoints that wrap results (kept optional)."""

    items: list[TeamMessageSummary]
    total: int = Field(description="Total matching records (for pagination).")
