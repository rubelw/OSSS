
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uuid


class UnitStandardMapBase(BaseModel):
    unit_id: uuid.UUID
    standard_id: uuid.UUID

    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
        populate_by_name=True,
    )

class UnitStandardMapCreate(UnitStandardMapBase): ...
class UnitStandardMapUpdate(UnitStandardMapBase): ...


class UnitStandardMapRead(UnitStandardMapBase):
    id: uuid.UUID
