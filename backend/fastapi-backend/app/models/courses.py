from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class Course(Base):
        __tablename__ = "courses"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
school_id = Column("school_id", UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
subject_id = Column("subject_id", UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="SET NULL"))
name = Column("name", Text, nullable=False)
code = Column("code", Text)
credit_hours = Column("credit_hours", Numeric(4,2))
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
