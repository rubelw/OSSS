# OSSS/schemas/comm_search_index.py
from __future__ import annotations
from typing import Optional, List
from pydantic import Field
from OSSS.schemas.base import APIModel

class CommSearchIndexBase(APIModel):
    entity_type: str = Field(..., max_length=32)
    entity_id: str = Field(...)
    ts: Optional[str] = None  # raw tsvector as string, or omit if you prefer

class CommSearchIndexCreate(CommSearchIndexBase): pass
class CommSearchIndexReplace(CommSearchIndexBase): pass

class CommSearchIndexPatch(APIModel):
    entity_type: Optional[str] = None
    entity_id:   Optional[str] = None
    ts:         Optional[str] = None

class CommSearchIndexOut(CommSearchIndexBase):
    id: str

class CommSearchIndexList(APIModel):
    items: List[CommSearchIndexOut]
    total: int | None = None
    skip: int = 0
    limit: int = 100
