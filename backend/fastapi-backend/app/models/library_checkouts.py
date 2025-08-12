from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class LibraryCheckout(Base):
    __tablename__ = "library_checkouts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column("item_id", GUID(), ForeignKey("library_items.id", ondelete="CASCADE"), nullable=False)
    person_id = Column("person_id", GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    checked_out_on = Column("checked_out_on", Date, nullable=False)
    due_on = Column("due_on", Date, nullable=False)
    returned_on = Column("returned_on", Date)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
