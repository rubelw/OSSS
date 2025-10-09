from __future__ import annotations
from typing import Optional
from datetime import datetime

from .base import ORMModel


class EvaluationTemplateOut(ORMModel):
    id: str
    name: str
    for_role: Optional[str] = None
    version: int
    is_active: bool


class EvaluationSectionOut(ORMModel):
    id: str
    template_id: str
    title: str
    order_no: int


class EvaluationQuestionOut(ORMModel):
    id: str
    section_id: str
    text: str
    type: str
    scale_min: Optional[int] = None
    scale_max: Optional[int] = None
    weight: Optional[float] = None


class EvaluationCycleOut(ORMModel):
    id: str
    org_id: str
    name: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None


class EvaluationAssignmentOut(ORMModel):
    id: str
    cycle_id: str
    subject_user_id: str
    evaluator_user_id: str
    template_id: str
    status: Optional[str] = None


class EvaluationResponseOut(ORMModel):
    id: str
    assignment_id: str
    question_id: str
    value_num: Optional[float] = None
    value_text: Optional[str] = None
    comment: Optional[str] = None
    answered_at: Optional[datetime] = None


class EvaluationSignoffOut(ORMModel):
    id: str
    assignment_id: str
    signer_id: str
    signed_at: datetime
    note: Optional[str] = None


class EvaluationReportOut(ORMModel):
    id: str
    cycle_id: str
    scope: Optional[dict] = None
    generated_at: datetime
    file_id: Optional[str] = None
