# OSSS/db/models/document_permission.py
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy import Column, DateTime, ForeignKey, func, text
from sqlalchemy.orm import Mapped, mapped_column
from OSSS.db.base import Base, GUID
from typing import ClassVar

class DocumentPermission(Base):
    __tablename__ = "document_permissions"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __allow_unmapped__ = True  # keep NOTE out of mapper

    NOTE: ClassVar[str] = (
        "owner=division_of_technology_data; "
        "description=Stores document permissions records for the application. "
        "References related entities via: principal, resource. "
        "6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores document permissions records for the application. "
            "References related entities via: principal, resource. "
            "6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores document permissions records for the application. "
                "References related entities via: principal, resource. "
                "6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
            ),
        },
    }


    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    resource_type:  Mapped[str] = mapped_column(sa.String(20), nullable=False)    # e.g. folder|document
    resource_id:    Mapped[str] = mapped_column(GUID(),        nullable=False, index=True)
    principal_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)    # e.g. user|group|role
    principal_id:   Mapped[str] = mapped_column(GUID(),        nullable=False, index=True)
    permission:     Mapped[str] = mapped_column(sa.String(20), nullable=False)    # e.g. view|edit|manage

