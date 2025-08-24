from __future__ import annotations
from datetime import datetime
from .base import ORMBase

class GlAccountSegmentBase(ORMBase):
    account_id: str
    segment_id: str
    position: int

class GlAccountSegmentCreate(GlAccountSegmentBase):
    pass

class GlAccountSegmentUpdate(ORMBase):
    account_id: str
    position: int

class GlAccountSegmentOut(GlAccountSegmentBase):
    id: str
    created_at: datetime
    updated_at: datetime
