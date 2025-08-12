from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class LibraryFine(Base):
        __tablename__ = "library_fines"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
person_id = Column("person_id", UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
amount = Column("amount", Numeric(10,2), nullable=False)
reason = Column("reason", Text)
assessed_on = Column("assessed_on", Date, nullable=False)
paid_on = Column("paid_on", Date)
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
