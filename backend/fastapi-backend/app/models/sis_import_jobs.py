from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class SisImportJob(Base):
        __tablename__ = "sis_import_jobs"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
source = Column("source", Text, nullable=False)
status = Column("status", Text, nullable=False, server_default=text("'running'"))
started_at = Column("started_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
finished_at = Column("finished_at", DateTime(timezone=True))
counts = Column("counts", JSONB)
error_log = Column("error_log", Text)
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
