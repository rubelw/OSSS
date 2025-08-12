from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class TranscriptLine(Base):
        __tablename__ = "transcript_lines"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
student_id = Column("student_id", UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
course_id = Column("course_id", UUID(as_uuid=True), ForeignKey("courses.id", ondelete="SET NULL"))
term_id = Column("term_id", UUID(as_uuid=True), ForeignKey("academic_terms.id", ondelete="SET NULL"))
credits_attempted = Column("credits_attempted", Numeric(5,2))
credits_earned = Column("credits_earned", Numeric(5,2))
final_letter = Column("final_letter", Text)
final_numeric = Column("final_numeric", Numeric(6,3))
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
