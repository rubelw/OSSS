# OSSS/schemas/file.py
from __future__ import annotations

from typing import Optional, List
from datetime import datetime
from pydantic import Field

from OSSS.schemas.base import APIModel


# -----------------------------
# Base (shared fields)
# -----------------------------
class FileBase(APIModel):
    storage_key: str = Field(..., max_length=512, description="Internal storage key/path for the file")
    filename: str = Field(..., max_length=255, description="Original filename")
    size: Optional[int] = Field(None, ge=0, description="Size in bytes")
    mime_type: Optional[str] = Field(None, max_length=127)
    created_by: Optional[str] = Field(None, description="User UUID who created/uploaded the file")


# -----------------------------
# Create (POST)
# -----------------------------
class FileCreate(FileBase):
    pass


# -----------------------------
# Replace (PUT)
# -----------------------------
class FileReplace(FileBase):
    pass


# -----------------------------
# Patch (PATCH)
# -----------------------------
class FilePatch(APIModel):
    storage_key: Optional[str] = Field(None, max_length=512)
    filename: Optional[str] = Field(None, max_length=255)
    size: Optional[int] = Field(None, ge=0)
    mime_type: Optional[str] = Field(None, max_length=127)
    created_by: Optional[str] = None


# -----------------------------
# Read (GET)
# -----------------------------
class FileOut(FileBase):
    id: str
    created_at: datetime
    updated_at: datetime

    # Relationship summaries (optional; computed server-side if you want)
    meeting_links_count: Optional[int] = None
    policy_links_count: Optional[int] = None


# -----------------------------
# List wrapper
# -----------------------------
class FileList(APIModel):
    items: List[FileOut]
    total: Optional[int] = None
    skip: int = 0
    limit: int = 100


# -----------------------------
# Back-compat aliases (optional)
# -----------------------------
FileRead = FileOut
FileIn = FileCreate
FileUpdate = FilePatch
FilePut = FileReplace

__all__ = [
    "FileBase",
    "FileCreate",
    "FileReplace",
    "FilePatch",
    "FileOut",
    "FileList",
    # aliases
    "FileRead",
    "FileIn",
    "FileUpdate",
    "FilePut",
]
