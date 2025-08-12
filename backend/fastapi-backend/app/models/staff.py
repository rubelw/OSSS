from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class Staff(Base):
        __tablename__ = "staff"


id = Column("id", UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True)
employee_number = Column("employee_number", Text, unique=True)
title = Column("title", Text)
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
