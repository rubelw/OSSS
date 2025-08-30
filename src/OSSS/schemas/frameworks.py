
from pydantic import BaseModel, Field, ConfigDict
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

    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
        populate_by_name=True,
    )

class FrameworkCreate(FrameworkBase): ...
class FrameworkUpdate(FrameworkBase): ...


class FrameworkRead(FrameworkBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
