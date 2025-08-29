# OSSS/schemas/student.py
from __future__ import annotations

from typing import Optional, List
from datetime import datetime
from pydantic import Field
from OSSS.schemas.base import APIModel


# -----------------------------
# Lightweight nested person (read-only)
# -----------------------------
class StudentPersonLink(APIModel):
    id: str
    first_name: str
    last_name: str

    model_config = {"from_attributes": True}


# -----------------------------
# Base (shared write fields)
# -----------------------------
class StudentBase(APIModel):
    student_number: Optional[str] = None
    graduation_year: Optional[int] = None


# -----------------------------
# Create (POST)
# -----------------------------
class StudentCreate(StudentBase):
    # required by model
    person_id: str = Field(..., description="FK to persons.id")


# -----------------------------
# Replace (PUT)
# -----------------------------
class StudentReplace(StudentBase):
    # required by model
    person_id: str = Field(..., description="FK to persons.id")


# -----------------------------
# Patch (PATCH)
# -----------------------------
class StudentPatch(APIModel):
    person_id: Optional[str] = None
    student_number: Optional[str] = None
    graduation_year: Optional[int] = None


# -----------------------------
# Read (GET)
# -----------------------------
class StudentOut(StudentBase):
    id: str
    person_id: str
    created_at: datetime
    updated_at: datetime

    # joined relationship (read-only)
    person: Optional[StudentPersonLink] = None

    model_config = {"from_attributes": True}


# -----------------------------
# List wrapper
# -----------------------------
class StudentList(APIModel):
    items: List[StudentOut]
    total: Optional[int] = None
    skip: int = 0
    limit: int = 100


# -----------------------------
# Back-compat aliases (if your generators expect them)
# -----------------------------
StudentRead = StudentOut
StudentIn = StudentCreate
StudentUpdate = StudentPatch

__all__ = [
    "StudentPersonLink",
    "StudentBase",
    "StudentCreate",
    "StudentReplace",
    "StudentPatch",
    "StudentOut",
    "StudentList",
    "StudentRead",
    "StudentIn",
    "StudentUpdate",
]
