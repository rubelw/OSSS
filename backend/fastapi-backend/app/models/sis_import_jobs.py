from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
import sqlalchemy as sa

from sqlalchemy.orm import relationship
from .base import Base, GUID, JSONB, UUIDMixin


class SisImportJob(UUIDMixin, Base):
    __tablename__ = "sis_import_jobs"
    source = Column("source", Text, nullable=False)
    status = Column("status", Text, nullable=False, server_default=text("'running'"))
    started_at = Column("started_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    finished_at = Column("finished_at", DateTime(timezone=True))
    counts = Column("counts", JSONB())
    error_log = Column("error_log", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
