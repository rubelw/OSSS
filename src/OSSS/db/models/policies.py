# src/OSSS/db/model/policies.py
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional, List

import sqlalchemy as sa
from sqlalchemy import String, Boolean, Text, Integer, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID, TSVectorType


class Policy(UUIDMixin, Base):
    __tablename__ = "policies"

    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[Optional[str]] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=sa.text("'active'")
    )

    versions: Mapped[List["PolicyVersion"]]= relationship(
        "PolicyVersion",
        back_populates="policy",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PolicyVersion.version_no",
        lazy="selectin",
    )

    __table_args__ = (
        sa.Index("ix_policies_org", "org_id"),
    )


class PolicyVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "policy_versions"

    policy_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    content: Mapped[Optional[str]] = mapped_column(Text)
    effective_date: Mapped[Optional[date]] = mapped_column(Date)
    supersedes_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("policy_versions.id", ondelete="SET NULL")
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("users.id")
    )

    policy: Mapped["Policy"] = relationship(
        "Policy", back_populates="versions", lazy="joined"
    )
    supersedes: Mapped[Optional["PolicyVersion"]] = relationship(
        "PolicyVersion",
        remote_side="PolicyVersion.id",
        lazy="joined",
        viewonly=True,
    )

    __table_args__ = (
        sa.Index("ix_policy_versions_policy", "policy_id"),
    )


class PolicyLegalRef(UUIDMixin, Base):
    __tablename__ = "policy_legal_refs"

    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False
    )
    citation: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(1024))

    __table_args__ = (
        sa.Index("ix_policy_legal_refs_version", "policy_version_id"),
    )


class PolicyComment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "policy_comments"

    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL")
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=sa.text("'public'")
    )

    __table_args__ = (
        sa.Index("ix_policy_comments_version", "policy_version_id"),
    )


class PolicyWorkflow(UUIDMixin, Base):
    __tablename__ = "policy_workflows"

    policy_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.text("true")
    )

    steps: Mapped[List["PolicyWorkflowStep"]] = relationship(
        "PolicyWorkflowStep",
        back_populates="workflow",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PolicyWorkflowStep.step_no",
        lazy="selectin",
    )

    __table_args__ = (
        sa.Index("ix_policy_workflows_policy", "policy_id"),
    )


class PolicyWorkflowStep(UUIDMixin, Base):
    __tablename__ = "policy_workflow_steps"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policy_workflows.id", ondelete="CASCADE"), nullable=False
    )
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    approver_type: Mapped[str] = mapped_column(String(20), nullable=False)  # user|group|role
    approver_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID())
    rule: Mapped[Optional[str]] = mapped_column(String(50))

    workflow: Mapped["PolicyWorkflow"] = relationship(
        "PolicyWorkflow", back_populates="steps", lazy="joined"
    )

    __table_args__ = (
        sa.UniqueConstraint("workflow_id", "step_no", name="uq_policy_workflow_step_no"),
        sa.Index("ix_policy_workflow_steps_wf", "workflow_id"),
    )


class PolicyApproval(UUIDMixin, Base):
    __tablename__ = "policy_approvals"

    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policy_workflow_steps.id", ondelete="CASCADE"), nullable=False
    )
    approver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("users.id")
    )
    decision: Mapped[Optional[str]] = mapped_column(String(16))
    decided_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    comment: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        sa.UniqueConstraint("policy_version_id", "step_id", name="uq_policy_approval_step"),
        sa.Index("ix_policy_approvals_version", "policy_version_id"),
    )


class PolicyPublication(Base):
    __tablename__ = "policy_publications"

    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policy_versions.id", ondelete="CASCADE"), primary_key=True
    )
    published_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    public_url: Mapped[Optional[str]] = mapped_column(String(1024))
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.text("false")
    )


class PolicyFile(Base):
    __tablename__ = "policy_files"

    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policy_versions.id", ondelete="CASCADE"), primary_key=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True
    )


class PolicySearchIndex(Base):
    __tablename__ = "policy_search_index"

    policy_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policies.id", ondelete="CASCADE"), primary_key=True
    )
    ts: Mapped[Optional[str]] = mapped_column(TSVectorType())

    __table_args__ = (
        sa.Index("ix_policy_search_gin", "ts", postgresql_using="gin"),
    )
