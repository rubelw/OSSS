from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class MealTransaction(Base):
    __tablename__ = "meal_transactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column("account_id", GUID(), ForeignKey("meal_accounts.id", ondelete="CASCADE"), nullable=False)
    transacted_at = Column("transacted_at", DateTime(timezone=True), nullable=False)
    amount = Column("amount", Numeric(10,2), nullable=False)
    description = Column("description", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
