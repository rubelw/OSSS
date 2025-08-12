from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class TestAdministration(Base):
        __tablename__ = "test_administrations"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
test_id = Column("test_id", UUID(as_uuid=True), ForeignKey("standardized_tests.id", ondelete="CASCADE"), nullable=False)
administration_date = Column("administration_date", Date, nullable=False)
school_id = Column("school_id", UUID(as_uuid=True), ForeignKey("schools.id", ondelete="SET NULL"))
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
