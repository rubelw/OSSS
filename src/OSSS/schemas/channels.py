# schemas/channel.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field

from .base import ORMBase


class ChannelCreate(BaseModel):
    org_id: str
    name: str
    audience: Literal["public", "staff", "board"] = Field(default="public")
    description: Optional[str] = None


class ChannelOut(ORMBase):
    id: str
    org_id: str
    name: str
    audience: Literal["public", "staff", "board"]
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
