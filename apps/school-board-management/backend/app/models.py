from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime, Boolean, ForeignKey, Text, Enum, Date, UniqueConstraint
from datetime import datetime
from .db import Base
import enum

class Role(enum.Enum):
    ADMIN = "ADMIN"
    CLERK = "CLERK"
    MEMBER = "MEMBER"
    PUBLIC = "PUBLIC"

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.PUBLIC, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class MeetingStatus(enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"

class Meeting(Base):
    __tablename__ = "meetings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    start_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    location: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[MeetingStatus] = mapped_column(Enum(MeetingStatus), default=MeetingStatus.DRAFT)
    livestream_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    agenda_items = relationship("AgendaItem", back_populates="meeting", cascade="all, delete-orphan")
    motions = relationship("Motion", back_populates="meeting", cascade="all, delete-orphan")

class AgendaItem(Base):
    __tablename__ = "agenda_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("agenda_items.id"), nullable=True)
    order_no: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(255))
    body_md: Mapped[str] = mapped_column(Text, default="")
    consent: Mapped[bool] = mapped_column(Boolean, default=False)
    executive_session: Mapped[bool] = mapped_column(Boolean, default=False)

    meeting = relationship("Meeting", back_populates="agenda_items")
    # explicit self-referential wiring
    parent = relationship("AgendaItem", remote_side=[id], back_populates="children")
    children = relationship("AgendaItem", back_populates="parent", cascade="all, delete-orphan")

class MotionStatus(enum.Enum):
    PROPOSED = "PROPOSED"
    PASSED = "PASSED"
    FAILED = "FAILED"
    TABLED = "TABLED"

class Motion(Base):
    __tablename__ = "motions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), index=True)
    agenda_item_id: Mapped[int | None] = mapped_column(ForeignKey("agenda_items.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    mover_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    seconder_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[MotionStatus] = mapped_column(Enum(MotionStatus), default=MotionStatus.PROPOSED)

    meeting = relationship("Meeting", back_populates="motions")
    votes = relationship("Vote", back_populates="motion", cascade="all, delete-orphan")

class VoteChoice(enum.Enum):
    AYE = "AYE"
    NAY = "NAY"
    ABSTAIN = "ABSTAIN"
    ABSENT = "ABSENT"

class Vote(Base):
    __tablename__ = "votes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    motion_id: Mapped[int] = mapped_column(ForeignKey("motions.id"), index=True)
    voter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    choice: Mapped[VoteChoice] = mapped_column(Enum(VoteChoice))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    motion = relationship("Motion", back_populates="votes")

class PolicyStatus(enum.Enum):
    DRAFT = "DRAFT"
    ADOPTED = "ADOPTED"
    RETIRED = "RETIRED"

class Policy(Base):
    __tablename__ = "policies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[PolicyStatus] = mapped_column(Enum(PolicyStatus), default=PolicyStatus.DRAFT)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # points to one PolicyVersion
    current_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("policy_versions.id"), unique=True, nullable=True
    )

    # disambiguate: policies.id -> policy_versions.policy_id
    versions = relationship(
        "PolicyVersion",
        back_populates="policy",
        foreign_keys=lambda: [PolicyVersion.policy_id],
        primaryjoin=lambda: Policy.id == PolicyVersion.policy_id,
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    # convenience pointer to the current version via policies.current_version_id
    current_version = relationship(
        "PolicyVersion",
        foreign_keys=lambda: [Policy.current_version_id],
        primaryjoin=lambda: Policy.current_version_id == PolicyVersion.id,
        uselist=False,
        post_update=True,
        lazy="selectin",
    )

    __table_args__ = (UniqueConstraint('code', name='uq_policy_code'),)

class PolicyVersion(Base):
    __tablename__ = "policy_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # disambiguate: policy_versions.policy_id -> policies.id
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id"), index=True)

    version_no: Mapped[int] = mapped_column(Integer, default=1)
    body_md: Mapped[str] = mapped_column(Text)

    # self-reference for redlines
    redline_from_id: Mapped[int | None] = mapped_column(ForeignKey("policy_versions.id"), nullable=True)

    adopted_on: Mapped[Date | None] = mapped_column(Date)
    effective_on: Mapped[Date | None] = mapped_column(Date)

    policy = relationship(
        "Policy",
        back_populates="versions",
        foreign_keys=lambda: [PolicyVersion.policy_id],
        primaryjoin=lambda: PolicyVersion.policy_id == Policy.id,
        lazy="selectin",
    )

    redline_from = relationship(
        "PolicyVersion",
        remote_side=lambda: [PolicyVersion.id],
        foreign_keys=lambda: [PolicyVersion.redline_from_id],
    )