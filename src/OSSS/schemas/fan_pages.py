# src/OSSS/schemas/fan_pages.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- Base ----------
class FanPageBase(BaseModel):
    """Fields shared by create/read/update."""

    # required in DB; nullable for Update
    school_id: Optional[str] = Field(
        default=None,
        description="GUID of the School this page belongs to.",
    )

    title: Optional[str] = Field(default=None, max_length=255)
    content_md: Optional[str] = None
    published: bool = False


# ---------- Create / Update ----------
class FanPageCreate(FanPageBase):
    """Payload for creating a FanPage."""
    # make school_id required on create
    school_id: str


class FanPageUpdate(BaseModel):
    """Partial update (PATCH) for a FanPage."""
    school_id: Optional[str] = None
    title: Optional[str] = Field(default=None, max_length=255)
    content_md: Optional[str] = None
    published: Optional[bool] = None


# ---------- Read ----------
class FanPageRead(FanPageBase):
    """Object returned from the API."""
    id: str
    created_at: datetime
    updated_at: datetime

    # Pydantic v2: allow from ORM
    model_config = ConfigDict(from_attributes=True)


# ---------- Filters ----------
class FanPageFilters(BaseModel):
    """
    Standard list filters used by the dynamic router.

    - Provide exact-match lists for id / school_id
    - `published` toggles by boolean
    - `title__ilike` is a case-insensitive contains match
    - `q` is a free-text search (router may map it to title/content)
    - `order_by` accepts fields with optional direction, e.g.:
        ["created_at desc", "title asc"]
    """
    id: Optional[List[str]] = None
    school_id: Optional[List[str]] = None
    published: Optional[bool] = None
    title__ilike: Optional[str] = None
    q: Optional[str] = None

    # pagination + sorting (kept generic to match other schemas)
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)
    order_by: Optional[List[str]] = Field(
        default=None,
        description="List of ORDER BY clauses, e.g. ['created_at desc', 'title asc']",
    )


__all__ = [
    "FanPageBase",
    "FanPageCreate",
    "FanPageUpdate",
    "FanPageRead",
    "FanPageFilters",
]
