from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class IepPlan(Base):
        __tablename__ = "iep_plans"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
special_ed_case_id = Column("special_ed_case_id", UUID(as_uuid=True), ForeignKey("special_education_cases.id", ondelete="CASCADE"), nullable=False)
effective_start = Column("effective_start", Date, nullable=False)
effective_end = Column("effective_end", Date)
summary = Column("summary", Text)
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
