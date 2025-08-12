from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class Incident(Base):
        __tablename__ = "incidents"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
school_id = Column("school_id", UUID(as_uuid=True), ForeignKey("schools.id", ondelete="SET NULL"))
occurred_at = Column("occurred_at", DateTime(timezone=True), nullable=False)
behavior_code = Column("behavior_code", Text, ForeignKey("behavior_codes.code", ondelete="RESTRICT"), nullable=False)
description = Column("description", Text)
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
