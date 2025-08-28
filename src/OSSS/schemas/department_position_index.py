# OSSS/schemas/department_position_index.py
from __future__ import annotations

from typing import Optional, List
from datetime import datetime
from pydantic import Field

from OSSS.schemas.base import APIModel


# -----------------------------
# Base (shared fields)
# -----------------------------
class DepartmentPositionIndexBase(APIModel):
    department_id: str = Field(..., description="UUID of Department")
    position_id: str = Field(..., description="UUID of HRPosition")


# -----------------------------
# Create (POST)
# -----------------------------
class DepartmentPositionIndexCreate(DepartmentPositionIndexBase):
    pass


# -----------------------------
# Replace (PUT)
# -----------------------------
class DepartmentPositionIndexReplace(DepartmentPositionIndexBase):
    pass


# -----------------------------
# Patch (PATCH)
# -----------------------------
class DepartmentPositionIndexPatch(APIModel):
    department_id: Optional[str] = None
    position_id: Optional[str] = None


# -----------------------------
# Read (GET)
# -----------------------------
class DepartmentPositionIndexOut(DepartmentPositionIndexBase):
    id: str
    created_at: datetime


# -----------------------------
# List wrapper
# -----------------------------
class DepartmentPositionIndexList(APIModel):
    items: List[DepartmentPositionIndexOut]
    total: Optional[int] = None
    skip: int = 0
    limit: int = 100


# -----------------------------
# Back-compat aliases (optional)
# -----------------------------
DepartmentPositionIndexRead = DepartmentPositionIndexOut
DepartmentPositionIndexIn = DepartmentPositionIndexCreate
DepartmentPositionIndexUpdate = DepartmentPositionIndexPatch
DepartmentPositionIndexPut = DepartmentPositionIndexReplace

__all__ = [
    "DepartmentPositionIndexBase",
    "DepartmentPositionIndexCreate",
    "DepartmentPositionIndexReplace",
    "DepartmentPositionIndexPatch",
    "DepartmentPositionIndexOut",
    "DepartmentPositionIndexList",
    # aliases
    "DepartmentPositionIndexRead",
    "DepartmentPositionIndexIn",
    "DepartmentPositionIndexUpdate",
    "DepartmentPositionIndexPut",
]
