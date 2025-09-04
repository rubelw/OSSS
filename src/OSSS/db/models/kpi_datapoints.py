from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class KPIDatapoint(UUIDMixin, Base):
    note: str = 'owner=division_of_technology_data; description=Stores kpi datapoints records for the application. References related entities via: kpi. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.'

    __tablename__ = "kpi_datapoints"

    __table_args__ = {'comment': 'Stores kpi datapoints records for the application. References related entities via: kpi. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.', 'info': {'description': 'Stores kpi datapoints records for the application. References related entities via: kpi. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.'}}

    kpi_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("kpis.id", ondelete="CASCADE"), nullable=False
    )
    as_of: Mapped[date] = mapped_column(sa.Date, nullable=False)
    value: Mapped[float] = mapped_column(sa.Float, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(sa.Text)

    kpi: Mapped["KPI"] = relationship("KPI", back_populates="datapoints", lazy="joined")

