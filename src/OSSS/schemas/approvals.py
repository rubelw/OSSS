
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uuid


class ApprovalBase(BaseModel):
    proposal_id: uuid.UUID
    association_id: uuid.UUID
    approved_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    status: Optional[str] = "active"

    class Config:
        orm_mode = True


class ApprovalCreate(ApprovalBase): ...
class ApprovalUpdate(ApprovalBase): ...


class ApprovalRead(ApprovalBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
