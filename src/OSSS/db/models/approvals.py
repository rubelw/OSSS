
from __future__ import annotations

from typing import Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid
from typing import ClassVar
from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID, ts_cols


class Approval(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "approvals"
    __allow_unmapped__ = True  # keep NOTE out of SQLAlchemy mapper

    NOTE: ClassVar[str] = (
        "owner=board_of_education_governing_board; "
        "description=Stores approvals records for the application. "
        "References related entities via: association, proposal. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores approvals records for the application. "
            "References related entities via: association, proposal. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores approvals records for the application. "
                "References related entities via: association, proposal. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
            ),
        },
    }

    association_id: Mapped[str] = mapped_column(GUID(), nullable=False, index=True)

    approved_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    expires_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True))
    status: Mapped[str] = mapped_column(sa.Enum("active", "expired", "revoked", name="approval_status", native_enum=False), nullable=False, server_default="active")

    # NEW: real FK to proposals.id
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        sa.ForeignKey("proposals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    updated_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())

    # relationship back to Proposal
    proposal: Mapped["Proposal"] = relationship(
        "Proposal",
        back_populates="approvals",
        lazy="joined",
    )