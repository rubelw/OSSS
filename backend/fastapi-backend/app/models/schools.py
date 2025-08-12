from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class School(Base):
        __tablename__ = "schools"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
district_id = Column("district_id", UUID(as_uuid=True), ForeignKey("districts.id", ondelete="CASCADE"), nullable=False)
name = Column("name", Text, nullable=False)
school_code = Column("school_code", Text, unique=True)
type = Column("type", Text)
timezone = Column("timezone", Text)
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
