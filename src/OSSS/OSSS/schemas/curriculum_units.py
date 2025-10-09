
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uuid


class CurriculumUnitBase(BaseModel):
    curriculum_id: uuid.UUID
    title: str
    order_index: int
    summary: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata_json")

    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
        populate_by_name=True,
    )

class CurriculumUnitCreate(CurriculumUnitBase): ...
class CurriculumUnitUpdate(CurriculumUnitBase): ...


class CurriculumUnitRead(CurriculumUnitBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
