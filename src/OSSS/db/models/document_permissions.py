# OSSS/db/models/document_permission.py
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column
from OSSS.db.base import Base, GUID

class DocumentPermission(Base):
    __tablename__ = "document_permissions"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    resource_type:  Mapped[str] = mapped_column(sa.String(20), nullable=False)    # e.g. folder|document
    resource_id:    Mapped[str] = mapped_column(GUID(),        nullable=False, index=True)
    principal_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)    # e.g. user|group|role
    principal_id:   Mapped[str] = mapped_column(GUID(),        nullable=False, index=True)
    permission:     Mapped[str] = mapped_column(sa.String(20), nullable=False)    # e.g. view|edit|manage

    __table_args__ = (
        sa.UniqueConstraint(
            "resource_type", "resource_id", "principal_type", "principal_id", "permission",
            name="uq_document_permissions_tuple",
        ),
        sa.Index("ix_docperm_resource", "resource_type", "resource_id"),
        sa.Index("ix_docperm_principal", "principal_type", "principal_id"),
    )
