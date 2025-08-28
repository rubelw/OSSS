# OSSS/schemas/policy_file.py
from __future__ import annotations
from typing import List
from datetime import datetime
from pydantic import Field
from OSSS.schemas.base import APIModel

class PolicyFileBase(APIModel):
    policy_version_id: str = Field(..., description="UUID of the policy version")
    file_id: str = Field(..., description="UUID of the linked file")

class PolicyFileCreate(PolicyFileBase): pass
class PolicyFileReplace(PolicyFileBase): pass  # symmetric; pair stays the same

class PolicyFilePatch(APIModel):
    # nothing meaningful to patch besides future non-key columns
    pass

class PolicyFileOut(APIModel):
    id: str
    policy_version_id: str
    file_id: str
    created_at: datetime

class PolicyFileList(APIModel):
    items: List[PolicyFileOut]
    total: int | None = None
    skip: int = 0
    limit: int = 100
