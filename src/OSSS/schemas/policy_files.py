# schemas/policyfile.py
from __future__ import annotations

from pydantic import BaseModel
from .base import ORMBase


class PolicyFileCreate(BaseModel):
    policy_version_id: str
    file_id: str


class PolicyFileOut(ORMBase):
    policy_version_id: str
    file_id: str
