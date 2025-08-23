from __future__ import annotations
from datetime import datetime, date

from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer, Float, Date, ForeignKey
from .base import Base, UUIDMixin, GUID, JSONB, TSVectorType
import uuid


class Plan(UUIDMixin, Base):
    __tablename__ = "plans"
    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cycle_start: Mapped[Optional["date"]] = mapped_column(Date)  # type: ignore
    cycle_end: Mapped[Optional["date"]] = mapped_column(Date)  # type: ignore
    status: Mapped[Optional[str]] = mapped_column(String(32))
    goals: Mapped[list["Goal"]] = relationship(back_populates="plan", cascade="all, delete-orphan")

class Goal(UUIDMixin, Base):
    __tablename__ = "goals"
    plan_id: Mapped[str] = mapped_column(GUID(), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    plan: Mapped[Plan] = relationship(back_populates="goals")
    objectives: Mapped[list["Objective"]] = relationship(back_populates="goal", cascade="all, delete-orphan")

class Objective(UUIDMixin, Base):
    __tablename__ = "objectives"
    goal_id: Mapped[str] = mapped_column(GUID(), ForeignKey("goals.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    goal: Mapped[Goal] = relationship(back_populates="objectives")

class Initiative(UUIDMixin, Base):
    __tablename__ = "initiatives"
    objective_id: Mapped[str] = mapped_column(GUID(), ForeignKey("objectives.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    owner_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id"))
    due_date: Mapped[Optional["date"]] = mapped_column(Date)  # type: ignore
    status: Mapped[Optional[str]] = mapped_column(String(32))
    priority: Mapped[Optional[str]] = mapped_column(String(16))

class KPI(UUIDMixin, Base):
    __tablename__ = "kpis"
    goal_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("goals.id", ondelete="SET NULL"))
    objective_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("objectives.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(32))
    target: Mapped[Optional[float]] = mapped_column(Float)
    baseline: Mapped[Optional[float]] = mapped_column(Float)
    direction: Mapped[Optional[str]] = mapped_column(String(8))  # up|down

class KPIDatapoint(UUIDMixin, Base):
    __tablename__ = "kpi_datapoints"
    kpi_id: Mapped[str] = mapped_column(GUID(), ForeignKey("kpis.id", ondelete="CASCADE"), nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)  # type: ignore
    value: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)

class Scorecard(UUIDMixin, Base):
    __tablename__ = "scorecards"
    plan_id: Mapped[str] = mapped_column(GUID(), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

class ScorecardKPI(Base):
    __tablename__ = "scorecard_kpis"
    scorecard_id: Mapped[str] = mapped_column(GUID(), ForeignKey("scorecards.id", ondelete="CASCADE"), primary_key=True)
    kpi_id: Mapped[str] = mapped_column(GUID(), ForeignKey("kpis.id", ondelete="CASCADE"), primary_key=True)
    display_order: Mapped[Optional[int]] = mapped_column(Integer)

class PlanAssignment(Base):
    __tablename__ = "plan_assignments"
    entity_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    entity_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    assignee_type: Mapped[str] = mapped_column(String(20), primary_key=True)  # user|group|role
    assignee_id: Mapped[str] = mapped_column(GUID(), primary_key=True)

class PlanAlignment(UUIDMixin, Base):
    __tablename__ = "plan_alignments"
    agenda_item_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("agenda_items.id", ondelete="SET NULL"))
    policy_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("policies.id", ondelete="SET NULL"))
    objective_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("objectives.id", ondelete="SET NULL"))
    note: Mapped[Optional[str]] = mapped_column(Text)

class PlanFilter(UUIDMixin, Base):
    __tablename__ = "plan_filters"
    plan_id: Mapped[str] = mapped_column(GUID(), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    criteria: Mapped[Optional[dict]] = mapped_column(JSONB())

class PlanSearchIndex(Base):
    __tablename__ = "plan_search_index"
    plan_id: Mapped[str] = mapped_column(GUID(), ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True)
    ts: Mapped[Optional[str]] = mapped_column(TSVectorType())
