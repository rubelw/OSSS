from __future__ import annotations

from typing import Optional, Dict, Any
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
# Back-compat aliases
# -----------------------------
# Back-compat aliases
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
    "EntityTagOut",
    "EntityTagIn",
    "EntityTagUpdate",
    "EntityTagReplace",
]
