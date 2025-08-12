from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class StateReportingSnapshot(Base):
        __tablename__ = "state_reporting_snapshots"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
as_of_date = Column("as_of_date", Date, nullable=False)
scope = Column("scope", Text)
payload = Column("payload", JSONB)
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
