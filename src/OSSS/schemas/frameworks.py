
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uuid


class FrameworkBase(BaseModel):
    code: str
    name: str
    edition: Optional[str] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata_json")

    class Config:
        allow_population_by_field_name = True
        orm_mode = True


class FrameworkCreate(FrameworkBase): ...
class FrameworkUpdate(FrameworkBase): ...


class FrameworkRead(FrameworkBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
