from __future__ import annotations

from typing import Optional, List, ClassVar
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID
from ._helpers import ts_cols


class ProposalDocument(UUIDMixin, Base):
    __tablename__ = "proposal_documents"
    __allow_unmapped__ = True

    NOTE: ClassVar[str] = (
        "owner=board_of_education_governing_board; "
        "description=Stores cic proposal documents records for the application. "
        "References related entities via: document, proposal. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores cic proposal documents records for the application. "
            "References related entities via: document, proposal. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores cic proposal documents records for the application. "
                "References related entities via: document, proposal. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
            ),
        },
    }

    proposal_id = sa.Column(
        GUID(), sa.ForeignKey("proposals.id", ondelete="CASCADE"), nullable=False, index=True
    )

    document_id = sa.Column(
        GUID(), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )

    file_uri = sa.Column(sa.Text)
    label = sa.Column(sa.Text)

    created_at, updated_at = ts_cols()

    # relationships
    proposal: Mapped["Proposal"] = relationship(
        "Proposal",
        back_populates="documents",  # must match Proposal.reviews below
        foreign_keys="ProposalDocument.proposal_id",
    )

    document: Mapped[Optional["Document"]] = relationship(
        "Document", back_populates="proposal_links", lazy="joined"
    )
