from __future__ import annotations
from datetime import datetime, date

from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Text, Integer, Date, ForeignKey, TIMESTAMP
from .base import Base, UUIDMixin, TimestampMixin, GUID, TSVectorType
import uuid
import sqlalchemy as sa

class Policy(UUIDMixin, Base):
    __tablename__ = "policies"
    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    versions: Mapped[list["PolicyVersion"]] = relationship(back_populates="policy", cascade="all, delete-orphan")

class PolicyVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "policy_versions"
    policy_id: Mapped[str] = mapped_column(GUID(), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    effective_date: Mapped[Optional["date"]] = mapped_column(Date)  # type: ignore
    supersedes_version_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("policy_versions.id", ondelete="SET NULL"))
    created_by: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id"))
    policy: Mapped[Policy] = relationship(back_populates="versions")

class PolicyLegalRef(UUIDMixin, Base):
    __tablename__ = "policy_legal_refs"
    policy_version_id: Mapped[str] = mapped_column(GUID(), ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False)
    citation: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(1024))

class PolicyComment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "policy_comments"
    policy_version_id: Mapped[str] = mapped_column(GUID(), ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="public")

class PolicyWorkflow(UUIDMixin, Base):
    __tablename__ = "policy_workflows"
    policy_id: Mapped[str] = mapped_column(GUID(), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

class PolicyWorkflowStep(UUIDMixin, Base):
    __tablename__ = "policy_workflow_steps"
    workflow_id: Mapped[str] = mapped_column(GUID(), ForeignKey("policy_workflows.id", ondelete="CASCADE"), nullable=False)
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    approver_type: Mapped[str] = mapped_column(String(20), nullable=False)
    approver_id: Mapped[Optional[str]] = mapped_column(GUID())
    rule: Mapped[Optional[str]] = mapped_column(String(50))

class PolicyApproval(UUIDMixin, Base):
    __tablename__ = "policy_approvals"
    policy_version_id: Mapped[str] = mapped_column(GUID(), ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False)
    step_id: Mapped[str] = mapped_column(GUID(), ForeignKey("policy_workflow_steps.id", ondelete="CASCADE"), nullable=False)
    approver_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id"))
    decision: Mapped[Optional[str]] = mapped_column(String(16))
    decided_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))  # type: ignore
    comment: Mapped[Optional[str]] = mapped_column(Text)

class PolicyPublication(Base):
    __tablename__ = "policy_publications"
    policy_version_id: Mapped[str] = mapped_column(GUID(), ForeignKey("policy_versions.id", ondelete="CASCADE"), primary_key=True)
    published_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)  # type: ignore
    public_url: Mapped[Optional[str]] = mapped_column(String(1024))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

class PolicyFile(Base):
    __tablename__ = "policy_files"
    policy_version_id: Mapped[str] = mapped_column(GUID(), ForeignKey("policy_versions.id", ondelete="CASCADE"), primary_key=True)
    file_id: Mapped[str] = mapped_column(GUID(), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)

class PolicySearchIndex(Base):
    __tablename__ = "policy_search_index"
    policy_id: Mapped[str] = mapped_column(GUID(), ForeignKey("policies.id", ondelete="CASCADE"), primary_key=True)
    ts: Mapped[Optional[str]] = mapped_column(TSVectorType())
