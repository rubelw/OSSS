from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

# Shared config to allow ORM -> Pydantic
class Orm(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# -------- Activity --------
class ActivityIn(BaseModel):
    school_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    is_active: Optional[bool] = True

# Create payload (same fields as ActivityIn)
class ActivityCreate(ActivityIn):
    pass

class ActivityOut(Orm):
    id: str
    school_id: Optional[str]
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
