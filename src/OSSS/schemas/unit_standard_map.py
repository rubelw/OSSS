
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uuid


class UnitStandardMapBase(BaseModel):
    unit_id: uuid.UUID
    standard_id: uuid.UUID

    class Config:
        orm_mode = True


class UnitStandardMapCreate(UnitStandardMapBase): ...
class UnitStandardMapUpdate(UnitStandardMapBase): ...


class UnitStandardMapRead(UnitStandardMapBase):
    id: uuid.UUID
