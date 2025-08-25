from __future__ import annotations
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, model_validator

from .base import ORMModel


class CICProposalDocumentCreate(BaseModel):
    proposal_id: str
    document_id: Optional[str] = None  # link to an existing Document
    file_uri: Optional[str] = None     # or an external URI
    label: Optional[str] = None

    @model_validator(mode="after")
    def _require_source(self):
        # Require at least one of document_id or file_uri
        if not (self.document_id or self.file_uri):
            raise ValueError("Either document_id or file_uri must be provided.")
        return self


class CICProposalDocumentOut(ORMModel):
    id: str
    proposal_id: str
    document_id: Optional[str] = None
    file_uri: Optional[str] = None
    label: Optional[str] = None
    created_at: datetime
    updated_at: datetime
