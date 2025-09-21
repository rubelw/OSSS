
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class FanPageBase(BaseModel):
    school_id: str
    slug: str
    title: Optional[str] = None
    content_md: Optional[str] = None
    published: bool = False
    class Config:
        from_attributes = True

class FanPageCreate(FanPageBase):
    id: Optional[str] = None

class FanPageRead(FanPageBase):
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class FanAppSettingBase(BaseModel):
    school_id: str
    theme: Optional[dict] = None
    features: Optional[dict] = None
    class Config:
        from_attributes = True

class FanAppSettingCreate(FanAppSettingBase):
    id: Optional[str] = None

class FanAppSettingRead(FanAppSettingBase):
    id: str
    updated_at: Optional[datetime] = None
