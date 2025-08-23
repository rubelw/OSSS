from __future__ import annotations

from datetime import datetime, date, time
from typing import Optional, Any

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base for all Pydantic models that parse from SQLAlchemy instances."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TimestampMixin(BaseModel):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
