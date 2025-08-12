from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class LibraryHold(Base):
    __tablename__ = "library_holds"
    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column("item_id", GUID(), ForeignKey("library_items.id", ondelete="CASCADE"), nullable=False)
    person_id = Column("person_id", GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    placed_on = Column("placed_on", Date, nullable=False)
    expires_on = Column("expires_on", Date)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("item_id", "person_id", name="uq_library_hold"), )
