from __future__ import annotations
from datetime import datetime
from typing import Optional

from .base import ORMModel, TimestampMixin


class UserBase(ORMModel):
    username: str
    email: str


class UserCreate(UserBase):
    pass


class UserUpdate(ORMModel):
    username: Optional[str] = None
    email: Optional[str] = None


class UserOut(UserBase, TimestampMixin):
    id: str
