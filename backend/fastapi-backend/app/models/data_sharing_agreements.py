from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID


class DataSharingAgreement(Base):
    __tablename__ = "data_sharing_agreements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    vendor = Column("vendor", Text, nullable=False)
    scope = Column("scope", Text)
    start_date = Column("start_date", Date)
    end_date = Column("end_date", Date)
    notes = Column("notes", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
