from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from typing import Optional, List
from .models import MeetingStatus, VoteChoice, PolicyStatus

class AgendaItemIn(BaseModel):
    parent_id: Optional[int] = None
    order_no: int = 0
    title: str
    body_md: str = ""
    consent: bool = False
    executive_session: bool = False

class AgendaItem(AgendaItemIn):
    id: int
    model_config = ConfigDict(from_attributes=True)

class MeetingIn(BaseModel):
    title: str
    start_at: datetime
    location: str = ""
    status: MeetingStatus = MeetingStatus.DRAFT
    livestream_url: Optional[str] = None

class Meeting(MeetingIn):
    id: int
    agenda_items: List[AgendaItem] = []
    model_config = ConfigDict(from_attributes=True)

class MotionIn(BaseModel):
    agenda_item_id: Optional[int] = None
    text: str

class VoteIn(BaseModel):
    choice: VoteChoice

class PolicyIn(BaseModel):
    code: str
    title: str
    status: PolicyStatus = PolicyStatus.DRAFT
    category: Optional[str] = None

class Policy(BaseModel):
    id: int
    code: str
    title: str
    status: PolicyStatus
    category: Optional[str]
    model_config = ConfigDict(from_attributes=True)

class PolicyVersionMeta(BaseModel):
    id: int
    version_no: int
    adopted_on: Optional[date] = None
    effective_on: Optional[date] = None
    model_config = ConfigDict(from_attributes=True)

class PolicyDetail(Policy):
    versions: List[PolicyVersionMeta]

class PolicyVersionIn(BaseModel):
    policy_id: int
    version_no: int = 1
    body_md: str
    redline_from_id: Optional[int] = None
    adopted_on: Optional[date] = None
    effective_on: Optional[date] = None

class PolicyVersionBody(BaseModel):
    id: int
    policy_id: int
    version_no: int
    body_md: str
    adopted_on: Optional[date] = None
    effective_on: Optional[date] = None
    model_config = ConfigDict(from_attributes=True)
