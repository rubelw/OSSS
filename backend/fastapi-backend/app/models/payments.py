from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column("invoice_id", GUID(), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    paid_on = Column("paid_on", Date, nullable=False)
    amount = Column("amount", Numeric(10,2), nullable=False)
    method = Column("method", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
