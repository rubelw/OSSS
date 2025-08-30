
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uuid


class ProposalBase(BaseModel):
    district_id: Optional[uuid.UUID] = None
    association_id: Optional[uuid.UUID] = None
    title: str
    summary: Optional[str] = None
    status: Optional[str] = "draft"
    submitted_at: Optional[datetime] = None
    attributes: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
        populate_by_name=True,
    )

class ProposalCreate(ProposalBase): ...
class ProposalUpdate(ProposalBase): ...


class ProposalRead(ProposalBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
