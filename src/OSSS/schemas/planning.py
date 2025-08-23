from __future__ import annotations
from typing import Optional
from datetime import date

from .base import ORMModel


class PlanBase(ORMModel):
    org_id: str
    name: str
    cycle_start: Optional[date] = None
    cycle_end: Optional[date] = None
    status: Optional[str] = None


class PlanOut(PlanBase):
    id: str


class GoalBase(ORMModel):
    plan_id: str
    name: str
    description: Optional[str] = None


class GoalOut(GoalBase):
    id: str


class ObjectiveBase(ORMModel):
    goal_id: str
    name: str
    description: Optional[str] = None


class ObjectiveOut(ObjectiveBase):
    id: str


class KPIBase(ORMModel):
    name: str
    goal_id: Optional[str] = None
    objective_id: Optional[str] = None
    unit: Optional[str] = None
    target: Optional[float] = None
    baseline: Optional[float] = None
    direction: Optional[str] = None  # up|down


class KPIOut(KPIBase):
    id: str


class KPIDatapointOut(ORMModel):
    id: str
    kpi_id: str
    as_of: date
    value: float
    note: Optional[str] = None
