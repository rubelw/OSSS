# src/OSSS/db/models/meetings.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, List
import uuid

import sqlalchemy as sa
from sqlalchemy import String, Boolean, Text, Integer, ForeignKey, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID, TSVectorType


# -------------------------------
# Meetings
# -------------------------------
class Meeting(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "meetings"

    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    body_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("bodies.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    ends_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    location: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[Optional[str]] = mapped_column(String(32))
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    stream_url: Mapped[Optional[str]] = mapped_column(String(1024))

    agenda_items: Mapped[List["AgendaItem"]] = relationship(
        "AgendaItem",
        back_populates="meeting",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AgendaItem.position",
        lazy="selectin",
    )
    minutes: Mapped[List["Minutes"]] = relationship(
        "Minutes",
        back_populates="meeting",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Minutes.created_at",
        lazy="selectin",
    )

    __table_args__ = (
        sa.Index("ix_meetings_org", "org_id"),
        sa.Index("ix_meetings_body", "body_id"),
        sa.Index("ix_meetings_starts_at", "starts_at"),
    )


class MeetingPermission(Base):
    __tablename__ = "meeting_permissions"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True
    )
    principal_type: Mapped[str] = mapped_column(String(20), primary_key=True)  # user|group|role
    principal_id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True)
    permission: Mapped[str] = mapped_column(String(50), primary_key=True)


# -------------------------------
# Agenda
# -------------------------------
class AgendaItem(UUIDMixin, Base):
    __tablename__ = "agenda_items"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("agenda_items.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    linked_policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID())
    linked_objective_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID())
    time_allocated: Mapped[Optional[int]] = mapped_column(Integer)

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="agenda_items", lazy="joined")

    # self-referential hierarchy
    parent: Mapped[Optional["AgendaItem"]] = relationship(
        "AgendaItem",
        remote_side="AgendaItem.id",
        back_populates="children",
        foreign_keys=[parent_id],
        lazy="selectin",
    )
    children: Mapped[List["AgendaItem"]] = relationship(
        "AgendaItem",
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys=[parent_id],
        passive_deletes=True,
        lazy="selectin",
        order_by="AgendaItem.position",
    )

    __table_args__ = (
        sa.Index("ix_agenda_items_meeting", "meeting_id"),
        sa.Index("ix_agenda_items_parent", "parent_id"),
    )


class AgendaWorkflow(UUIDMixin, Base):
    __tablename__ = "agenda_workflows"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))

    steps: Mapped[List["AgendaWorkflowStep"]] = relationship(
        "AgendaWorkflowStep",
        back_populates="workflow",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="AgendaWorkflowStep.step_no",
    )


class AgendaWorkflowStep(UUIDMixin, Base):
    __tablename__ = "agenda_workflow_steps"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agenda_workflows.id", ondelete="CASCADE"), nullable=False
    )
    step_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    approver_type: Mapped[str] = mapped_column(String(20), nullable=False)
    approver_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID())
    rule: Mapped[Optional[str]] = mapped_column(String(50))

    workflow: Mapped["AgendaWorkflow"] = relationship("AgendaWorkflow", back_populates="steps", lazy="joined")

    __table_args__ = (sa.Index("ix_agenda_workflow_steps_wf", "workflow_id"),)


class AgendaItemApproval(UUIDMixin, Base):
    __tablename__ = "agenda_item_approvals"

    item_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agenda_items.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agenda_workflow_steps.id", ondelete="CASCADE"), nullable=False
    )
    approver_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("users.id"))
    decision: Mapped[Optional[str]] = mapped_column(String(16))
    decided_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    comment: Mapped[Optional[str]] = mapped_column(Text)

    item: Mapped["AgendaItem"] = relationship("AgendaItem", lazy="joined")
    step: Mapped["AgendaWorkflowStep"] = relationship("AgendaWorkflowStep", lazy="joined")

    __table_args__ = (sa.Index("ix_agenda_item_approvals_item", "item_id"),)


# -------------------------------
# Motions / Votes / Attendance
# -------------------------------
class Motion(UUIDMixin, Base):
    __tablename__ = "motions"

    agenda_item_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agenda_items.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    moved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("users.id"))
    seconded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("users.id"))
    passed: Mapped[Optional[bool]] = mapped_column(Boolean)
    tally_for: Mapped[Optional[int]] = mapped_column(Integer)
    tally_against: Mapped[Optional[int]] = mapped_column(Integer)
    tally_abstain: Mapped[Optional[int]] = mapped_column(Integer)

    agenda_item: Mapped["AgendaItem"] = relationship("AgendaItem", lazy="joined")


class Vote(UUIDMixin, Base):
    __tablename__ = "votes"

    motion_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("motions.id", ondelete="CASCADE"), nullable=False
    )
    voter_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[str] = mapped_column(String(16), nullable=False)

    motion: Mapped["Motion"] = relationship("Motion", lazy="joined")


class Attendance(Base):
    __tablename__ = "attendance"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[Optional[str]] = mapped_column(String(16))
    arrived_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    left_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    meeting: Mapped["Meeting"] = relationship("Meeting", lazy="joined")


# -------------------------------
# Minutes & files
# -------------------------------
class Minutes(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "minutes"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("users.id"))
    content: Mapped[Optional[str]] = mapped_column(Text)
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="minutes", lazy="joined")


class MeetingFile(Base):
    __tablename__ = "meeting_files"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True
    )
    caption: Mapped[Optional[str]] = mapped_column(String(255))


class AgendaItemFile(Base):
    __tablename__ = "agenda_item_files"

    agenda_item_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agenda_items.id", ondelete="CASCADE"), primary_key=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True
    )
    caption: Mapped[Optional[str]] = mapped_column(String(255))


class PersonalNote(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "personal_notes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    text: Mapped[Optional[str]] = mapped_column(Text)


class MeetingPublication(Base):
    __tablename__ = "meeting_publications"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True
    )
    published_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    public_url: Mapped[Optional[str]] = mapped_column(String(1024))
    archive_url: Mapped[Optional[str]] = mapped_column(String(1024))


class MeetingSearchIndex(Base):
    __tablename__ = "meeting_search_index"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True
    )
    ts: Mapped[Optional[str]] = mapped_column(TSVectorType())

    __table_args__ = (
        sa.Index("ix_meeting_search_gin", "ts", postgresql_using="gin"),
    )
