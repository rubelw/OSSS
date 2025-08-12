from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class TeacherSectionAssignment(Base):
        __tablename__ = "teacher_section_assignments"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
staff_id = Column("staff_id", UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
section_id = Column("section_id", UUID(as_uuid=True), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
role = Column("role", Text)
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
__table_args__ = (UniqueConstraint("staff_id", "section_id", name="uq_teacher_section"), )
