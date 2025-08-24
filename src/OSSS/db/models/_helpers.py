from __future__ import annotations

from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import mapped_column, Mapped

def ts_cols() -> tuple[Mapped[datetime], Mapped[datetime]]:
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )
    return created_at, updated_at
