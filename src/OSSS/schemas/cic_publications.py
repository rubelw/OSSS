from __future__ import annotations
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from .base import ORMModel


class CICPublicationCreate(BaseModel):
    meeting_id: str
    published_at: Optional[datetime] = None
    public_url: Optional[str] = None
    is_final: Optional[bool] = None


class CICPublicationOut(ORMModel):
    id: str
    meeting_id: str
    published_at: datetime
    public_url: Optional[str] = None
    is_final: bool
    created_at: datetime
    updated_at: datetime
