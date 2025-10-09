# OSSS/schemas/person.py
# Auto-generated-style — updated for Person.student relationship
from __future__ import annotations

from typing import Optional, List
from datetime import date, datetime
from pydantic import Field
from OSSS.schemas.base import APIModel


# -----------------------------
# Lightweight nested student (read-only)
# -----------------------------
class PersonStudentLink(APIModel):
    id: str
    student_number: Optional[str] = None
    graduation_year: Optional[int] = None

    model_config = {"from_attributes": True}


# -----------------------------
# Base (shared write fields)
# -----------------------------
class PersonBase(APIModel):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    middle_name: Optional[str] = None
    dob: Optional[date] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None


# -----------------------------
# Create (POST)
# -----------------------------
class PersonCreate(PersonBase):
    pass


# -----------------------------
# Replace (PUT)
# -----------------------------
class PersonReplace(PersonBase):
    pass


# -----------------------------
# Patch (PATCH)
# -----------------------------
class PersonPatch(APIModel):
    first_name: Optional[str] = Field(None, min_length=1)
    last_name: Optional[str] = Field(None, min_length=1)
    middle_name: Optional[str] = None
    dob: Optional[date] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None


# -----------------------------
# Read (GET)
# -----------------------------
class PersonOut(PersonBase):
    id: str
    created_at: datetime
    updated_at: datetime

    # Expose the 1:1 relationship as an optional nested link
    student: Optional[PersonStudentLink] = None

    model_config = {"from_attributes": True}


# -----------------------------
# List wrapper
# -----------------------------
class PersonList(APIModel):
    items: List[PersonOut]
    total: Optional[int] = None
    skip: int = 0
    limit: int = 100


__all__ = [
    "PersonStudentLink",
    "PersonBase",
    "PersonCreate",
    "PersonReplace",
    "PersonPatch",
    "PersonOut",
    "PersonList",
]
