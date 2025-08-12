from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class LibraryFine(Base):
    __tablename__ = "library_fines"
    id = Column(Integer, primary_key=True, autoincrement=True)
    person_id = Column("person_id", GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    amount = Column("amount", Numeric(10,2), nullable=False)
    reason = Column("reason", Text)
    assessed_on = Column("assessed_on", Date, nullable=False)
    paid_on = Column("paid_on", Date)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
