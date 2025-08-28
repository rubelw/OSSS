# OSSS/schemas/meeting_file.py
from __future__ import annotations

from typing import Optional, List
from pydantic import Field

from OSSS.schemas.base import APIModel


# -----------------------------
# Base (shared fields)
# -----------------------------
class MeetingFileBase(APIModel):
    meeting_id: str = Field(..., description="UUID of the Meeting")
    file_id: str = Field(..., description="UUID of the File")
    caption: Optional[str] = Field(None, max_length=255)


# -----------------------------
# Create (POST)
# -----------------------------
class MeetingFileCreate(MeetingFileBase):
    pass


# -----------------------------
# Replace (PUT)
# -----------------------------
class MeetingFileReplace(MeetingFileBase):
    pass


# -----------------------------
# Patch (PATCH)
# -----------------------------
class MeetingFilePatch(APIModel):
    meeting_id: Optional[str] = None
    file_id: Optional[str] = None
    caption: Optional[str] = Field(None, max_length=255)


# -----------------------------
# Read (GET)
# -----------------------------
class MeetingFileOut(APIModel):
    id: str
    meeting_id: str
    file_id: str
    caption: Optional[str] = None


# -----------------------------
# List wrapper
# -----------------------------
class MeetingFileList(APIModel):
    items: List[MeetingFileOut]
    total: Optional[int] = None
    skip: int = 0
    limit: int = 100


# -----------------------------
# Back-compat aliases (optional)
# -----------------------------
MeetingFileRead = MeetingFileOut
MeetingFileIn = MeetingFileCreate
MeetingFileUpdate = MeetingFilePatch
MeetingFilePut = MeetingFileReplace

__all__ = [
    "MeetingFileBase",
    "MeetingFileCreate",
    "MeetingFileReplace",
    "MeetingFilePatch",
    "MeetingFileOut",
    "MeetingFileList",
    # aliases
    "MeetingFileRead",
    "MeetingFileIn",
    "MeetingFileUpdate",
    "MeetingFilePut",
]
