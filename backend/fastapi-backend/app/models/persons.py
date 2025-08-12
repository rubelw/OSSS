from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class Person(Base):
        __tablename__ = "persons"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
first_name = Column("first_name", Text, nullable=False)
last_name = Column("last_name", Text, nullable=False)
middle_name = Column("middle_name", Text)
dob = Column("dob", Date)
email = Column("email", Text)
phone = Column("phone", Text)
gender = Column("gender", Text)
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
