from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class MealTransaction(Base):
        __tablename__ = "meal_transactions"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
account_id = Column("account_id", UUID(as_uuid=True), ForeignKey("meal_accounts.id", ondelete="CASCADE"), nullable=False)
transacted_at = Column("transacted_at", DateTime(timezone=True), nullable=False)
amount = Column("amount", Numeric(10,2), nullable=False)
description = Column("description", Text)
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
