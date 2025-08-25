# schemas/postattachment.py
from __future__ import annotations

from pydantic import BaseModel
from .base import ORMBase


class PostAttachmentCreate(BaseModel):
    post_id: str
    file_id: str


class PostAttachmentOut(ORMBase):
    post_id: str
    file_id: str
