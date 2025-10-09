# OSSS/schemas/policy_version.py
from __future__ import annotations

from typing import Optional, List
from datetime import datetime, date
from pydantic import Field

from OSSS.schemas.base import APIModel


# -----------------------------
# Base (shared fields)
# -----------------------------
class PolicyVersionBase(APIModel):
    policy_id: str = Field(..., description="UUID of the parent Policy")
    version_no: Optional[int] = Field(
        None, ge=1, description="Version number (DB default = 1 if omitted)"
    )
    content: Optional[str] = Field(None, description="Policy content (text/markdown/html)")
    effective_date: Optional[date] = Field(None, description="Date this version takes effect")
    supersedes_version_id: Optional[str] = Field(
        None, description="UUID of the prior PolicyVersion that this version supersedes"
    )
    created_by: Optional[str] = Field(None, description="UUID of the creating user")


# -----------------------------
# Create (POST)
# -----------------------------
class PolicyVersionCreate(PolicyVersionBase):
    # keep all fields as in Base; server will fill version_no default when omitted
    pass


# -----------------------------
# Replace (PUT)
# -----------------------------
class PolicyVersionReplace(PolicyVersionBase):
    # PUT expects a full replacement (same shape as Base)
    pass


# -----------------------------
# Patch (PATCH)
# -----------------------------
class PolicyVersionPatch(APIModel):
    policy_id: Optional[str] = None
    version_no: Optional[int] = Field(None, ge=1)
    content: Optional[str] = None
    effective_date: Optional[date] = None
    supersedes_version_id: Optional[str] = None
    created_by: Optional[str] = None


# -----------------------------
# Read (GET)
# -----------------------------
class PolicyVersionOut(PolicyVersionBase):
    id: str
    created_at: datetime
    updated_at: datetime

    # Optional lightweight relationship summaries (populate server-side if desired)
    files_count: Optional[int] = None


# -----------------------------
# List wrapper
# -----------------------------
class PolicyVersionList(APIModel):
    items: List[PolicyVersionOut]
    total: Optional[int] = None
    skip: int = 0
    limit: int = 100


# -----------------------------
# Back-compat aliases (optional)
# -----------------------------
PolicyVersionRead = PolicyVersionOut
PolicyVersionIn = PolicyVersionCreate
PolicyVersionUpdate = PolicyVersionPatch
PolicyVersionPut = PolicyVersionReplace

__all__ = [
    "PolicyVersionBase",
    "PolicyVersionCreate",
    "PolicyVersionReplace",
    "PolicyVersionPatch",
    "PolicyVersionOut",
    "PolicyVersionList",
    # aliases
    "PolicyVersionRead",
    "PolicyVersionIn",
    "PolicyVersionUpdate",
    "PolicyVersionPut",
]
