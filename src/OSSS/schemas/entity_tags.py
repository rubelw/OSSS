# schemas/entitytag.py
from __future__ import annotations

from pydantic import BaseModel

from .base import ORMBase


class EntityTagCreate(BaseModel):
    entity_type: str
    entity_id: str
    tag_id: str


class EntityTagOut(ORMBase):
    entity_type: str
    entity_id: str
    tag_id: str
