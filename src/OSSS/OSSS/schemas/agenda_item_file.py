# OSSS/schemas/agenda_item_file.py
from __future__ import annotations
from typing import Optional, List
from pydantic import Field
from OSSS.schemas.base import APIModel

class AgendaItemFileBase(APIModel):
    agenda_item_id: str = Field(...)
    file_id: str = Field(...)
    caption: Optional[str] = None

class AgendaItemFileCreate(AgendaItemFileBase): pass
class AgendaItemFileReplace(AgendaItemFileBase): pass

class AgendaItemFilePatch(APIModel):
    agenda_item_id: Optional[str] = None
    file_id: Optional[str] = None
    caption: Optional[str] = None

class AgendaItemFileOut(AgendaItemFileBase):
    id: str

class AgendaItemFileList(APIModel):
    items: List[AgendaItemFileOut]
    total: int | None = None
    skip: int = 0
    limit: int = 100
