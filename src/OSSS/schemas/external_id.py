from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel

from .base import ORMBase


class ExternalIdCreate(BaseModel):
    """Fields accepted on create/update."""
    entity_type: str          # e.g. "student", "staff", "course"
    entity_id: str            # GUID/UUID of the local entity
    system: str               # e.g. "clever", "classlink", "sis"
    external_id: str          # provider's identifier
    attributes: Optional[Dict[str, Any]] = None  # optional metadata


class ExternalIdOut(ORMBase):
    id: str
    entity_type: str
    entity_id: str
    system: str
    external_id: str
    created_at: datetime
    updated_at: datetime
