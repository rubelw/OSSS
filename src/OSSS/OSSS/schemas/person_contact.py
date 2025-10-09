# OSSS/schemas/person_contact.py
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import Field
from OSSS.schemas.base import APIModel

class PersonContactBase(APIModel):
    person_id: str = Field(...)
    contact_id: str = Field(...)
    label: Optional[str] = None
    is_primary: Optional[bool] = None
    is_emergency: Optional[bool] = None

class PersonContactCreate(PersonContactBase): pass
class PersonContactReplace(PersonContactBase):
    is_primary: bool = Field(...)
    is_emergency: bool = Field(...)
class PersonContactPatch(APIModel):
    label: Optional[str] = None
    is_primary: Optional[bool] = None
    is_emergency: Optional[bool] = None

class PersonContactOut(PersonContactBase):
    id: str
    created_at: datetime
    updated_at: datetime

class PersonContactList(APIModel):
    items: List[PersonContactOut]
    total: int | None = None
    skip: int = 0
    limit: int = 100
