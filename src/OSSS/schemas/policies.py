from __future__ import annotations
from typing import Optional
from datetime import datetime, date

from .base import ORMModel, TimestampMixin


class PolicyBase(ORMModel):
    org_id: str
    title: str
    code: Optional[str] = None
    status: str = "active"


class PolicyCreate(PolicyBase):
    pass


class PolicyOut(PolicyBase):
    id: str


class PolicyVersionBase(ORMModel):
    policy_id: str
    version_no: int = 1
    content: Optional[str] = None
    effective_date: Optional[date] = None
    supersedes_version_id: Optional[str] = None
    created_by: Optional[str] = None


class PolicyVersionCreate(PolicyVersionBase):
    pass


class PolicyVersionOut(PolicyVersionBase, TimestampMixin):
    id: str


class PolicyLegalRefOut(ORMModel):
    id: str
    policy_version_id: str
    citation: str
    url: Optional[str] = None


class PolicyCommentOut(ORMModel, TimestampMixin):
    id: str
    policy_version_id: str
    user_id: Optional[str] = None
    text: str
    visibility: str = "public"
