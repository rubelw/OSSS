
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uuid


class ProposalStandardMapBase(BaseModel):
    proposal_id: uuid.UUID
    standard_id: uuid.UUID
    strength: Optional[int] = None
    notes: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
        populate_by_name=True,
    )

class ProposalStandardMapCreate(ProposalStandardMapBase): ...
class ProposalStandardMapUpdate(ProposalStandardMapBase): ...


class ProposalStandardMapRead(ProposalStandardMapBase):
    id: uuid.UUID
