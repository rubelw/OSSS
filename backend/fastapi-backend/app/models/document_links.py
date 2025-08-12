from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID


class DocumentLink(Base):
    __tablename__ = "document_links"
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column("document_id", GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    entity_type = Column("entity_type", Text, nullable=False)
    entity_id = Column("entity_id", GUID(), nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
