from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class NurseVisit(Base):
        __tablename__ = "nurse_visits"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
student_id = Column("student_id", UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
visited_at = Column("visited_at", DateTime(timezone=True), nullable=False)
reason = Column("reason", Text)
disposition = Column("disposition", Text)
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
