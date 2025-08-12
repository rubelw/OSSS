from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class StudentSchoolEnrollment(Base):
        __tablename__ = "student_school_enrollments"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
student_id = Column("student_id", UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
school_id = Column("school_id", UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
entry_date = Column("entry_date", Date, nullable=False)
exit_date = Column("exit_date", Date)
status = Column("status", Text, nullable=False, server_default=text("'active'"))
exit_reason = Column("exit_reason", Text)
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
