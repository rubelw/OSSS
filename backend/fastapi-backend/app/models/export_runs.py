from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base


class ExportRun(Base):
    __tablename__ = "export_runs"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    export_name = Column("export_name", Text, nullable=False)
    ran_at = Column("ran_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    status = Column("status", Text, nullable=False, server_default=text("'success'"))
    file_uri = Column("file_uri", Text)
    error = Column("error", Text)
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
