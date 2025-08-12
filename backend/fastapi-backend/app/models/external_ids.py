from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class ExternalId(Base):
        __tablename__ = "external_ids"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
entity_type = Column("entity_type", Text, nullable=False)
entity_id = Column("entity_id", UUID(as_uuid=True), nullable=False)
system = Column("system", Text, nullable=False)
external_id = Column("external_id", Text, nullable=False)
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
__table_args__ = (UniqueConstraint("entity_type", "entity_id", "system", name="uq_external_ids"), )
