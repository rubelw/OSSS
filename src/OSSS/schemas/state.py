# src/OSSS/api/schemas/states.py  (Pydantic v2)
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, constr


# Shared/base fields (keep code here if you allow posting code with the body)
class StateBase(BaseModel):
    name: constr(min_length=1, max_length=64)  # type: ignore[type-arg]


# For create: if you POST code in body (rather than path), include it here.
class StateCreate(StateBase):
    code: constr(min_length=2, max_length=2, strip_whitespace=True)  # type: ignore[type-arg]


# For partial updates (e.g., PATCH); typically only name is mutable
class StateUpdate(BaseModel):
    name: Optional[constr(min_length=1, max_length=64)] = None  # type: ignore[type-arg]


# What you return from the API
class StateOut(BaseModel):
    code: str = Field(..., min_length=2, max_length=2)
    name: str

    model_config = ConfigDict(from_attributes=True)