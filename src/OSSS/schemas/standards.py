
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uuid


class StandardBase(BaseModel):
    framework_id: uuid.UUID
    code: str
    description: str
    parent_id: Optional[uuid.UUID] = None
    grade_band: Optional[str] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    attributes: Optional[Dict[str, Any]] = None

    class Config:
        orm_mode = True


class StandardCreate(StandardBase): ...
class StandardUpdate(StandardBase): ...


class StandardRead(StandardBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
