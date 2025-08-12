from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class GradingPeriod(Base):
        __tablename__ = "grading_periods"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
term_id = Column("term_id", UUID(as_uuid=True), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False)
name = Column("name", Text, nullable=False)
start_date = Column("start_date", Date, nullable=False)
end_date = Column("end_date", Date, nullable=False)
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
