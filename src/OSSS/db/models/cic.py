# src/OSSS/db/models/cic.py
from __future__ import annotations
from typing import Optional

from sqlalchemy import (
    Column,
    Text,
    Date,
    DateTime,
    Integer,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    TIMESTAMP,
    func,
    text,
)
from sqlalchemy.orm import relationship

from OSSS.db.base import Base, GUID, UUIDMixin


# Reusable timestamp columns (DB-driven defaults)
def ts_cols():
    return (
        Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
        Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )


class CICCommittee(UUIDMixin, Base):
    __tablename__ = "cic_committees"

    district_id = Column(GUID(), ForeignKey("districts.id", ondelete="SET NULL"))
    school_id   = Column(GUID(), ForeignKey("schools.id",   ondelete="SET NULL"))
    name        = Column(Text, nullable=False)
    description = Column(Text)
    status      = Column(Text, nullable=False, server_default=text("'active'"))

    created_at, updated_at = ts_cols()

    __table_args__ = (
        CheckConstraint(
            "(district_id IS NOT NULL) OR (school_id IS NOT NULL)",
            name="ck_cic_committee_scope",
        ),
    )

    memberships = relationship(
        "CICMembership", back_populates="committee", cascade="all, delete-orphan"
    )
    meetings = relationship(
        "CICMeeting", back_populates="committee", cascade="all, delete-orphan"
    )
    proposals = relationship(
        "CICProposal", back_populates="committee", cascade="all, delete-orphan"
    )


class CICMembership(UUIDMixin, Base):
    __tablename__ = "cic_memberships"

    committee_id  = Column(GUID(), ForeignKey("cic_committees.id", ondelete="CASCADE"), nullable=False)
    person_id     = Column(GUID(), ForeignKey("persons.id",        ondelete="CASCADE"), nullable=False)
    role          = Column(Text)  # chair, member, etc.
    start_date    = Column(Date)
    end_date      = Column(Date)
    voting_member = Column(Boolean, nullable=False, server_default=text("true"))

    created_at, updated_at = ts_cols()

    __table_args__ = (UniqueConstraint("committee_id", "person_id", name="uq_cic_membership_unique"),)

    committee = relationship("CICCommittee", back_populates="memberships")


class CICMeeting(UUIDMixin, Base):
    __tablename__ = "cic_meetings"

    committee_id = Column(GUID(), ForeignKey("cic_committees.id", ondelete="CASCADE"), nullable=False)
    title        = Column(Text, nullable=False)
    scheduled_at = Column(TIMESTAMP(timezone=True), nullable=False)
    ends_at      = Column(TIMESTAMP(timezone=True))
    location     = Column(Text)
    status       = Column(Text, nullable=False, server_default=text("'scheduled'"))
    is_public    = Column(Boolean, nullable=False, server_default=text("true"))

    created_at, updated_at = ts_cols()

    committee      = relationship("CICCommittee", back_populates="meetings")
    agenda_items   = relationship("CICAgendaItem",     back_populates="meeting",   cascade="all, delete-orphan")
    resolutions    = relationship("CICResolution",     back_populates="meeting",   cascade="all, delete-orphan")
    publications   = relationship("CICPublication",    back_populates="meeting",   cascade="all, delete-orphan")
    meeting_documents = relationship("CICMeetingDocument", back_populates="meeting", cascade="all, delete-orphan")


class CICAgendaItem(UUIDMixin, Base):
    __tablename__ = "cic_agenda_items"

    meeting_id   = Column(GUID(), ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False)
    parent_id    = Column(GUID(), ForeignKey("cic_agenda_items.id", ondelete="SET NULL"))
    position     = Column(Integer, nullable=False, server_default=text("0"))
    title        = Column(Text, nullable=False)
    description  = Column(Text)
    time_allocated_minutes = Column(Integer)
    subject_id   = Column(GUID(), ForeignKey("subjects.id", ondelete="SET NULL"))
    course_id    = Column(GUID(), ForeignKey("courses.id",  ondelete="SET NULL"))

    created_at, updated_at = ts_cols()

    __table_args__ = (UniqueConstraint("meeting_id", "position", name="uq_cic_agenda_position"),)

    meeting = relationship("CICMeeting", back_populates="agenda_items")

    # Self-referential tree
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

    agenda_item_id = Column(GUID(), ForeignKey("cic_agenda_items.id", ondelete="CASCADE"), nullable=False)
    text           = Column(Text, nullable=False)
    moved_by_id    = Column(GUID(), ForeignKey("persons.id", ondelete="SET NULL"))
    seconded_by_id = Column(GUID(), ForeignKey("persons.id", ondelete="SET NULL"))
    result         = Column(Text)  # passed|failed|tabled
    tally_for      = Column(Integer)
    tally_against  = Column(Integer)
    tally_abstain  = Column(Integer)

    created_at, updated_at = ts_cols()

    agenda_item = relationship("CICAgendaItem", back_populates="motions")
    votes = relationship("CICVote", back_populates="motion", cascade="all, delete-orphan")


class CICVote(UUIDMixin, Base):
    __tablename__ = "cic_votes"

    motion_id = Column(GUID(), ForeignKey("cic_motions.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(GUID(), ForeignKey("persons.id",     ondelete="CASCADE"), nullable=False)
    value     = Column(Text, nullable=False)  # yea|nay|abstain|absent

    created_at, updated_at = ts_cols()

    __table_args__ = (UniqueConstraint("motion_id", "person_id", name="uq_cic_vote_unique"),)

    motion = relationship("CICMotion", back_populates="votes")


class CICResolution(UUIDMixin, Base):
    __tablename__ = "cic_resolutions"

    meeting_id     = Column(GUID(), ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False)
    title          = Column(Text, nullable=False)
    summary        = Column(Text)
    effective_date = Column(Date)
    status         = Column(Text)  # adopted|rejected|tabled

    created_at, updated_at = ts_cols()

    meeting = relationship("CICMeeting", back_populates="resolutions")


class CICProposal(UUIDMixin, Base):
    __tablename__ = "cic_proposals"

    committee_id   = Column(GUID(), ForeignKey("cic_committees.id", ondelete="CASCADE"), nullable=False)
    submitted_by_id= Column(GUID(), ForeignKey("persons.id",        ondelete="SET NULL"))
    school_id      = Column(GUID(), ForeignKey("schools.id",        ondelete="SET NULL"))
    type           = Column(Text, nullable=False)  # new_course|course_change|materials_adoption|policy
    subject_id     = Column(GUID(), ForeignKey("subjects.id", ondelete="SET NULL"))
    course_id      = Column(GUID(), ForeignKey("courses.id",  ondelete="SET NULL"))
    title          = Column(Text, nullable=False)
    rationale      = Column(Text)
    status         = Column(Text, nullable=False, server_default=text("'draft'"))  # draft|under_review|approved|rejected|withdrawn
    submitted_at   = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    created_at, updated_at = ts_cols()

    committee = relationship("CICCommittee", back_populates="proposals")
    reviews   = relationship("CICProposalReview",   back_populates="proposal", cascade="all, delete-orphan")
    documents = relationship("CICProposalDocument", back_populates="proposal", cascade="all, delete-orphan")


class CICProposalReview(UUIDMixin, Base):
    __tablename__ = "cic_proposal_reviews"

    proposal_id = Column(GUID(), ForeignKey("cic_proposals.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = Column(GUID(), ForeignKey("persons.id",       ondelete="SET NULL"))
    decision    = Column(Text)  # approve|reject|revise
    decided_at  = Column(TIMESTAMP(timezone=True))
    comment     = Column(Text)

    created_at, updated_at = ts_cols()

    __table_args__ = (UniqueConstraint("proposal_id", "reviewer_id", name="uq_cic_proposal_reviewer"),)

    proposal = relationship("CICProposal", back_populates="reviews")


class CICProposalDocument(UUIDMixin, Base):
    __tablename__ = "cic_proposal_documents"

    proposal_id = Column(GUID(), ForeignKey("cic_proposals.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(GUID(), ForeignKey("documents.id",    ondelete="SET NULL"))
    file_uri    = Column(Text)
    label       = Column(Text)

    created_at, updated_at = ts_cols()

    proposal = relationship("CICProposal", back_populates="documents")


class CICMeetingDocument(UUIDMixin, Base):
    __tablename__ = "cic_meeting_documents"

    meeting_id  = Column(GUID(), ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(GUID(), ForeignKey("documents.id",    ondelete="SET NULL"))
    file_uri    = Column(Text)
    label       = Column(Text)

    created_at, updated_at = ts_cols()

    meeting = relationship("CICMeeting", back_populates="meeting_documents")


class CICPublication(UUIDMixin, Base):
    __tablename__ = "cic_publications"

    meeting_id   = Column(GUID(), ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False)
    published_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    public_url   = Column(Text)
    is_final     = Column(Boolean, nullable=False, server_default=text("false"))

    created_at, updated_at = ts_cols()

    meeting = relationship("CICMeeting", back_populates="publications")

