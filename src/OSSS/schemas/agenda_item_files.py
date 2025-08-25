# src/OSSS/schemas/agenda_item_files.py
from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from .base import ORMBase


class AgendaItemFileCreate(BaseModel):
    agenda_item_id: UUID
    file_id: UUID
    caption: Optional[str] = None


class AgendaItemFileOut(ORMBase):
    agenda_item_id: UUID
    file_id: UUID
    caption: Optional[str] = None
