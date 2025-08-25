from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from .base import ORMModel


class CICMeetingDocumentCreate(BaseModel):
    meeting_id: str = Field(..., description="ID of the CIC meeting this document belongs to")
    document_id: Optional[str] = Field(
        None, description="Optional reference to an internal document record"
    )
    file_uri: Optional[str] = Field(
        None, description="External file URI if not using an internal document"
    )
    label: Optional[str] = Field(None, description="Human-friendly label/title of the document")


class CICMeetingDocumentOut(ORMModel):
    id: str
    meeting_id: str
    document_id: Optional[str] = None
    file_uri: Optional[str] = None
    label: Optional[str] = None
    created_at: datetime
    updated_at: datetime
