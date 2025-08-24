from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, Literal


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# --- keep existing mixins, etc. ---

# Backward-compat alias (so older code importing ORMBase keeps working)
ORMBase = ORMModel

class TimestampMixin(BaseModel):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
