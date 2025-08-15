from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, Text, CHAR, Date, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .base import Base, GUID, UUIDMixin

class CICCommittee(UUIDMixin, Base):
    __tablename__ = "cic_committees"

    district_id = sa.Column(sa.CHAR(36), ForeignKey("districts.id", ondelete="SET NULL"), nullable=True)
    school_id = sa.Column(sa.CHAR(36), ForeignKey("schools.id", ondelete="SET NULL"), nullable=True)
    name = sa.Column(Text, nullable=False)
    description = sa.Column(Text, nullable=True)
    status = sa.Column(Text, nullable=False, server_default=text("'active'"))
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    __table_args__ = (
        CheckConstraint("(district_id IS NOT NULL) OR (school_id IS NOT NULL)", name="ck_cic_committee_scope"),
    )

    memberships = relationship("CICMembership", back_populates="committee", cascade="all, delete-orphan")
    meetings = relationship("CICMeeting", back_populates="committee", cascade="all, delete-orphan")
    proposals = relationship("CICProposal", back_populates="committee", cascade="all, delete-orphan")


class CICMembership(UUIDMixin, Base):
    __tablename__ = "cic_memberships"

    committee_id = Column(CHAR(36), ForeignKey("cic_committees.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(CHAR(36), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    role = Column(Text, nullable=True)  # chair, member, etc.
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    voting_member = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    __table_args__ = (
        UniqueConstraint("committee_id", "person_id", name="uq_cic_membership_unique"),
    )

    committee = relationship("CICCommittee", back_populates="memberships")

class CICMeeting(UUIDMixin, Base):
    __tablename__ = "cic_meetings"

    committee_id = Column(CHAR(36), ForeignKey("cic_committees.id", ondelete="CASCADE"), nullable=False)
    title = Column(Text, nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    location = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default=text("'scheduled'"))
    is_public = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    committee = relationship("CICCommittee", back_populates="meetings")
    agenda_items = relationship("CICAgendaItem", back_populates="meeting", cascade="all, delete-orphan")
    resolutions = relationship("CICResolution", back_populates="meeting", cascade="all, delete-orphan")
    publications = relationship("CICPublication", back_populates="meeting", cascade="all, delete-orphan")
    meeting_documents = relationship("CICMeetingDocument", back_populates="meeting", cascade="all, delete-orphan")

class CICAgendaItem(UUIDMixin, Base):
    __tablename__ = "cic_agenda_items"

    meeting_id = Column(CHAR(36), ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(CHAR(36), ForeignKey("cic_agenda_items.id", ondelete="SET NULL"), nullable=True)
    position = Column(Integer, nullable=False, server_default=text("0"))
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    time_allocated_minutes = Column(Integer, nullable=True)
    subject_id = Column(GUID(), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    course_id = Column(GUID(), ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    __table_args__ = (
        UniqueConstraint("meeting_id", "position", name="uq_cic_agenda_position"),
    )

    meeting = relationship("CICMeeting", back_populates="agenda_items")

    # ✅ FIX: reference the actual column via lambda; add explicit foreign_keys and inverse side
    parent = relationship(
        "CICAgendaItem",
        remote_side=lambda: [CICAgendaItem.id],
        back_populates="children",
        foreign_keys=lambda: [CICAgendaItem.parent_id],
    )
    children = relationship(
        "CICAgendaItem",
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys=lambda: [CICAgendaItem.parent_id],
        passive_deletes=True,
    )

    motions = relationship("CICMotion", back_populates="agenda_item", cascade="all, delete-orphan")

class CICMotion(UUIDMixin, Base):
    __tablename__ = "cic_motions"

    agenda_item_id = Column(CHAR(36), ForeignKey("cic_agenda_items.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    moved_by_id = Column(CHAR(36), ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    seconded_by_id = Column(CHAR(36), ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    result = Column(Text, nullable=True)  # passed|failed|tabled
    tally_for = Column(Integer, nullable=True)
    tally_against = Column(Integer, nullable=True)
    tally_abstain = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    agenda_item = relationship("CICAgendaItem", back_populates="motions")
    votes = relationship("CICVote", back_populates="motion", cascade="all, delete-orphan")

class CICVote(UUIDMixin, Base):
    __tablename__ = "cic_votes"

    motion_id = Column(CHAR(36), ForeignKey("cic_motions.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(CHAR(36), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    value = Column(Text, nullable=False)  # yea|nay|abstain|absent
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    __table_args__ = (
        UniqueConstraint("motion_id", "person_id", name="uq_cic_vote_unique"),
    )

    motion = relationship("CICMotion", back_populates="votes")

class CICResolution(UUIDMixin, Base):
    __tablename__ = "cic_resolutions"

    meeting_id = Column(CHAR(36), ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False)
    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    effective_date = Column(Date, nullable=True)
    status = Column(Text, nullable=True)  # adopted|rejected|tabled
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    meeting = relationship("CICMeeting", back_populates="resolutions")

class CICProposal(UUIDMixin, Base):
    __tablename__ = "cic_proposals"

    committee_id = Column(CHAR(36), ForeignKey("cic_committees.id", ondelete="CASCADE"), nullable=False)
    submitted_by_id = Column(CHAR(36), ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    school_id = Column(CHAR(36), ForeignKey("schools.id", ondelete="SET NULL"), nullable=True)
    type = Column(Text, nullable=False)  # new_course|course_change|materials_adoption|policy
    subject_id = Column(CHAR(36), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    course_id = Column(CHAR(36), ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    title = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default=text("'draft'"))  # draft|under_review|approved|rejected|withdrawn
    submitted_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    review_deadline = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    committee = relationship("CICCommittee", back_populates="proposals")
    reviews = relationship("CICProposalReview", back_populates="proposal", cascade="all, delete-orphan")
    documents = relationship("CICProposalDocument", back_populates="proposal", cascade="all, delete-orphan")

class CICProposalReview(UUIDMixin, Base):
    __tablename__ = "cic_proposal_reviews"

    proposal_id = Column(CHAR(36), ForeignKey("cic_proposals.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = Column(CHAR(36), ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    decision = Column(Text, nullable=True)  # approve|reject|revise
    decided_at = Column(DateTime(timezone=True), nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    __table_args__ = (
        UniqueConstraint("proposal_id", "reviewer_id", name="uq_cic_proposal_reviewer"),
    )

    proposal = relationship("CICProposal", back_populates="reviews")

class CICProposalDocument(UUIDMixin, Base):
    __tablename__ = "cic_proposal_documents"

    proposal_id = Column(CHAR(36), ForeignKey("cic_proposals.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(CHAR(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    file_uri = Column(Text, nullable=True)
    label = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    proposal = relationship("CICProposal", back_populates="documents")

class CICMeetingDocument(UUIDMixin, Base):
    __tablename__ = "cic_meeting_documents"

    meeting_id = Column(CHAR(36), ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(CHAR(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    file_uri = Column(Text, nullable=True)
    label = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    meeting = relationship("CICMeeting", back_populates="meeting_documents")


class CICPublication(UUIDMixin, Base):
    __tablename__ = "cic_publications"

    meeting_id = Column(CHAR(36), ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False)
    published_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    public_url = Column(Text, nullable=True)
    is_final = Column(Boolean, nullable=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    meeting = relationship("CICMeeting", back_populates="publications")
