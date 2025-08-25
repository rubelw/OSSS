from __future__ import annotations

from pydantic import BaseModel

from .base import ORMBase


class MeetingPermissionCreate(BaseModel):
    meeting_id: str
    principal_type: str  # "user" | "group" | "role"
    principal_id: str
    permission: str


class MeetingPermissionOut(ORMBase):
    meeting_id: str
    principal_type: str
    principal_id: str
    permission: str
