# schemas/classrank.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, conint

from .base import ORMBase


class ClassRankCreate(BaseModel):
    school_id: str
    term_id: str
    student_id: str
    rank: conint(ge=1)  # rank must be >= 1


class ClassRankOut(ORMBase):
    id: str
    school_id: str
    term_id: str
    student_id: str
    rank: int
    created_at: datetime
    updated_at: datetime
