from __future__ import annotations
from datetime import datetime, date

from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Text, Integer, ForeignKey, TIMESTAMP
from .base import Base, UUIDMixin, TimestampMixin, GUID, TSVectorType
import uuid
import sqlalchemy as sa


class Meeting(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "meetings"
    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    body_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("bodies.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)  # type: ignore
    ends_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))  # type: ignore
    location: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[Optional[str]] = mapped_column(String(32))
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    stream_url: Mapped[Optional[str]] = mapped_column(String(1024))

    agenda_items: Mapped[list["AgendaItem"]] = relationship(back_populates="meeting", cascade="all, delete-orphan")
    minutes: Mapped[list["Minutes"]] = relationship(back_populates="meeting", cascade="all, delete-orphan")

class MeetingPermission(Base):
    __tablename__ = "meeting_permissions"
    meeting_id: Mapped[str] = mapped_column(GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True)
    principal_type: Mapped[str] = mapped_column(String(20), primary_key=True)  # user|group|role
    principal_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    permission: Mapped[str] = mapped_column(String(50), primary_key=True)

class AgendaItem(UUIDMixin, Base):
    __tablename__ = "agenda_items"
    meeting_id: Mapped[str] = mapped_column(GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    parent_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("agenda_items.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    linked_policy_id: Mapped[Optional[str]] = mapped_column(GUID())
    linked_objective_id: Mapped[Optional[str]] = mapped_column(GUID())
    time_allocated: Mapped[Optional[int]] = mapped_column(Integer)

    meeting: Mapped[Meeting] = relationship(back_populates="agenda_items")
    # ✅ FIX: self-referential relationship using lambda to reference actual columns
    parent: Mapped[Optional["AgendaItem"]] = relationship(
        "AgendaItem",
        remote_side=lambda: [AgendaItem.id],  # reference the column attribute
        back_populates="children",
        foreign_keys=lambda: [AgendaItem.parent_id],  # be explicit on the FK column
    )
    children: Mapped[list["AgendaItem"]] = relationship(
        "AgendaItem",
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys=lambda: [AgendaItem.parent_id],
        passive_deletes=True,
    )

class AgendaWorkflow(UUIDMixin, Base):
    __tablename__ = "agenda_workflows"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    steps: Mapped[list["AgendaWorkflowStep"]] = relationship(back_populates="workflow", cascade="all, delete-orphan")

class AgendaWorkflowStep(UUIDMixin, Base):
    __tablename__ = "agenda_workflow_steps"
    workflow_id: Mapped[str] = mapped_column(GUID(), ForeignKey("agenda_workflows.id", ondelete="CASCADE"), nullable=False)
    step_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approver_type: Mapped[str] = mapped_column(String(20), nullable=False)
    approver_id: Mapped[Optional[str]] = mapped_column(GUID())
    rule: Mapped[Optional[str]] = mapped_column(String(50))
    workflow: Mapped[AgendaWorkflow] = relationship(back_populates="steps")

class AgendaItemApproval(UUIDMixin, Base):
    __tablename__ = "agenda_item_approvals"
    item_id: Mapped[str] = mapped_column(GUID(), ForeignKey("agenda_items.id", ondelete="CASCADE"), nullable=False)
    step_id: Mapped[str] = mapped_column(GUID(), ForeignKey("agenda_workflow_steps.id", ondelete="CASCADE"), nullable=False)
    approver_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id"))
    decision: Mapped[Optional[str]] = mapped_column(String(16))
    decided_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))  # type: ignore
    comment: Mapped[Optional[str]] = mapped_column(Text)

class Motion(UUIDMixin, Base):
    __tablename__ = "motions"
    agenda_item_id: Mapped[str] = mapped_column(GUID(), ForeignKey("agenda_items.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    moved_by_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id"))
    seconded_by_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id"))
    passed: Mapped[Optional[bool]] = mapped_column(Boolean)
    tally_for: Mapped[Optional[int]] = mapped_column(Integer)
    tally_against: Mapped[Optional[int]] = mapped_column(Integer)
    tally_abstain: Mapped[Optional[int]] = mapped_column(Integer)

class Vote(UUIDMixin, Base):
    __tablename__ = "votes"
    motion_id: Mapped[str] = mapped_column(GUID(), ForeignKey("motions.id", ondelete="CASCADE"), nullable=False)
    voter_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    value: Mapped[str] = mapped_column(String(16), nullable=False)

class Attendance(Base):
    __tablename__ = "attendance"
    meeting_id: Mapped[str] = mapped_column(GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[Optional[str]] = mapped_column(String(16))
    arrived_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))  # type: ignore
    left_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))  # type: ignore

class Minutes(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "minutes"
    meeting_id: Mapped[str] = mapped_column(GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id"))
    content: Mapped[Optional[str]] = mapped_column(Text)
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))  # type: ignore
    meeting: Mapped[Meeting] = relationship(back_populates="minutes")

class MeetingFile(Base):
    __tablename__ = "meeting_files"
    meeting_id: Mapped[str] = mapped_column(GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True)
    file_id: Mapped[str] = mapped_column(GUID(), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
    caption: Mapped[Optional[str]] = mapped_column(String(255))

class AgendaItemFile(Base):
    __tablename__ = "agenda_item_files"
    agenda_item_id: Mapped[str] = mapped_column(GUID(), ForeignKey("agenda_items.id", ondelete="CASCADE"), primary_key=True)
    file_id: Mapped[str] = mapped_column(GUID(), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
    caption: Mapped[Optional[str]] = mapped_column(String(255))

class PersonalNote(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "personal_notes"
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    text: Mapped[Optional[str]] = mapped_column(Text)

class MeetingPublication(Base):
    __tablename__ = "meeting_publications"
    meeting_id: Mapped[str] = mapped_column(GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True)
    published_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)  # type: ignore
    public_url: Mapped[Optional[str]] = mapped_column(String(1024))
    archive_url: Mapped[Optional[str]] = mapped_column(String(1024))

class MeetingSearchIndex(Base):
    __tablename__ = "meeting_search_index"
    meeting_id: Mapped[str] = mapped_column(GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True)
    ts: Mapped[Optional[str]] = mapped_column(TSVectorType())  # ORM placeholder
