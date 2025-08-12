from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class StandardizedTest(Base):
        __tablename__ = "standardized_tests"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
name = Column("name", Text, nullable=False)
subject = Column("subject", Text)
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
