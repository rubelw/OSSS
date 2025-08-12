from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID


class ExportRun(Base):
    __tablename__ = "export_runs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    export_name = Column("export_name", Text, nullable=False)
    ran_at = Column("ran_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    status = Column("status", Text, nullable=False, server_default=text("'success'"))
    file_uri = Column("file_uri", Text)
    error = Column("error", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
