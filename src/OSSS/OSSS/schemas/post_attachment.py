# OSSS/schemas/post_attachment.py
from __future__ import annotations
from typing import List, Optional
from pydantic import Field
from OSSS.schemas.base import APIModel

class PostAttachmentBase(APIModel):
    post_id: str = Field(...)
    file_id: str = Field(...)

class PostAttachmentCreate(PostAttachmentBase):
    pass

class PostAttachmentReplace(PostAttachmentBase):
    pass

class PostAttachmentPatch(APIModel):
    post_id: Optional[str] = None
    file_id: Optional[str] = None

class PostAttachmentOut(PostAttachmentBase):
    id: str

class PostAttachmentList(APIModel):
    items: List[PostAttachmentOut]
    total: int | None = None
    skip: int = 0
    limit: int = 100
