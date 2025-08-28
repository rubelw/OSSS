from __future__ import annotations

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field

# -----------------------------
# Base (shared fields)
# -----------------------------
class EntityTagBase(BaseModel):
    entity_type: str = Field(..., min_length=1, max_length=50, description="Type of the tagged entity")
    entity_id: str = Field(..., description="GUID/UUID of the entity being tagged")
    tag_id: str = Field(..., description="GUID/UUID of the Tag")
    # attributes: Optional[Dict[str, Any]] = None  # uncomment if added to model

# -----------------------------
# Create (POST)
# -----------------------------
class EntityTagCreate(EntityTagBase):
    pass

# -----------------------------
# Replace (PUT)
# -----------------------------
class EntityTagPut(EntityTagBase):
    pass

# -----------------------------
# Patch (PATCH)
# -----------------------------
class EntityTagPatch(BaseModel):
    entity_type: Optional[str] = Field(None, min_length=1, max_length=50)
    entity_id: Optional[str] = None
    tag_id: Optional[str] = None
    # attributes: Optional[Dict[str, Any]] = None

# -----------------------------
# Read (GET)
# -----------------------------
class EntityTagRead(EntityTagBase):
    id: str
    model_config = ConfigDict(from_attributes=True)

# -----------------------------
# Collections
# -----------------------------
# Simple alias that FastAPI accepts as response_model
EntityTagList = List[EntityTagRead]

# If you prefer an object wrapper (e.g., for pagination), use this instead:
# class EntityTagList(BaseModel):
#     items: List[EntityTagRead] = Field(default_factory=list)
#     total: Optional[int] = None
#     model_config = ConfigDict(from_attributes=True)

# -----------------------------
# Back-compat aliases (old names)
# -----------------------------
EntityTagOut = EntityTagRead        # response
EntityTagIn = EntityTagCreate       # create
EntityTagUpdate = EntityTagPatch    # patch
EntityTagReplace = EntityTagPut     # put  <-- REQUIRED

__all__ = [
    "EntityTagBase",
    "EntityTagCreate",
    "EntityTagPut",
    "EntityTagPatch",
    "EntityTagRead",
    "EntityTagList",
    "EntityTagOut",
    "EntityTagIn",
    "EntityTagUpdate",
    "EntityTagReplace",
]
