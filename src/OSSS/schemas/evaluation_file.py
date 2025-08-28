# OSSS/schemas/evaluation_file.py
from __future__ import annotations
from typing import List, Optional
from pydantic import Field
from OSSS.schemas.base import APIModel

class EvaluationFileBase(APIModel):
    assignment_id: str = Field(...)
    file_id: str = Field(...)

class EvaluationFileCreate(EvaluationFileBase): pass
class EvaluationFileReplace(EvaluationFileBase): pass

class EvaluationFilePatch(APIModel):
    assignment_id: Optional[str] = None
    file_id: Optional[str] = None

class EvaluationFileOut(EvaluationFileBase):
    id: str

class EvaluationFileList(APIModel):
    items: List[EvaluationFileOut]
    total: int | None = None
    skip: int = 0
    limit: int = 100
