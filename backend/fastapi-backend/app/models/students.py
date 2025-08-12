from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class Student(Base):
        __tablename__ = "students"


id = Column("id", UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True)
student_number = Column("student_number", Text, unique=True)
graduation_year = Column("graduation_year", Integer)
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
