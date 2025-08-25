# schemas/policyworkflow.py
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class PolicyWorkflowCreate(BaseModel):
    policy_id: str
    name: str
    active: bool = True


class PolicyWorkflowOut(ORMBase):
    id: str
    policy_id: str
    name: str
    active: bool
