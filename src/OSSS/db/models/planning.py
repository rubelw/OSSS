# src/OSSS/db/models/planning.py
from __future__ import annotations

import uuid
from datetime import date
from typing import Optional, List

import sqlalchemy as sa
from sqlalchemy import String, Text, Integer, Float, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TSVectorType


# -------------------------------
# Plan
# -------------------------------
class Plan(UUIDMixin, Base):
    __tablename__ = "plans"

    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cycle_start: Mapped[Optional[date]] = mapped_column(Date)
    cycle_end: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[Optional[str]] = mapped_column(String(32))

    goals: Mapped[List["Goal"]] = relationship(
        "Goal",
        back_populates="plan",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Goal.name",
        lazy="selectin",
    )

    # Optional: a single search row per plan
    search_index: Mapped[Optional["PlanSearchIndex"]] = relationship(
        "PlanSearchIndex",
        back_populates="plan",
        cascade="all, delete-orphan",
        uselist=False,
        passive_deletes=True,
    )

    __table_args__ = (
        sa.Index("ix_plans_org", "org_id"),
    )


# -------------------------------
# Goal / Objective / Initiative
# -------------------------------
class Goal(UUIDMixin, Base):
    __tablename__ = "goals"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    plan: Mapped["Plan"] = relationship("Plan", back_populates="goals", lazy="joined")

    objectives: Mapped[List["Objective"]] = relationship(
        "Objective",
        back_populates="goal",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Objective.name",
        lazy="selectin",
    )

    # KPIs attached directly to a Goal (optional; some KPIs may be for an Objective instead)
    kpis: Mapped[List["KPI"]] = relationship(
        "KPI",
        back_populates="goal",
        primaryjoin="Goal.id == KPI.goal_id",
        lazy="selectin",
    )

    __table_args__ = (
        sa.Index("ix_goals_plan", "plan_id"),
    )


class Objective(UUIDMixin, Base):
    __tablename__ = "objectives"

    goal_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    goal: Mapped["Goal"] = relationship("Goal", back_populates="objectives", lazy="joined")

    initiatives: Mapped[List["Initiative"]] = relationship(
        "Initiative",
        back_populates="objective",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Initiative.name",
        lazy="selectin",
    )

    # KPIs attached to this Objective
    kpis: Mapped[List["KPI"]] = relationship(
        "KPI",
        back_populates="objective",
        primaryjoin="Objective.id == KPI.objective_id",
        lazy="selectin",
    )

    __table_args__ = (
        sa.Index("ix_objectives_goal", "goal_id"),
    )


class Initiative(UUIDMixin, Base):
    __tablename__ = "initiatives"

    objective_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("objectives.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("users.id"))
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[Optional[str]] = mapped_column(String(32))
    priority: Mapped[Optional[str]] = mapped_column(String(16))

    objective: Mapped["Objective"] = relationship("Objective", back_populates="initiatives", lazy="joined")
    owner: Mapped[Optional["User"]] = relationship("User", lazy="joined")  # type: ignore[name-defined]

    __table_args__ = (
        sa.Index("ix_initiatives_objective", "objective_id"),
        sa.Index("ix_initiatives_owner", "owner_id"),
    )


# -------------------------------
# KPI & datapoints
# -------------------------------
class KPI(UUIDMixin, Base):
    __tablename__ = "kpis"

    goal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("goals.id", ondelete="SET NULL")
    )
    objective_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("objectives.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(32))
    target: Mapped[Optional[float]] = mapped_column(sa.Float)
    baseline: Mapped[Optional[float]] = mapped_column(sa.Float)
    direction: Mapped[Optional[str]] = mapped_column(String(8))  # up|down

    goal: Mapped[Optional["Goal"]] = relationship("Goal", back_populates="kpis", lazy="joined")
    objective: Mapped[Optional["Objective"]] = relationship("Objective", back_populates="kpis", lazy="joined")

    datapoints: Mapped[List["KPIDatapoint"]] = relationship(
        "KPIDatapoint",
        back_populates="kpi",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="KPIDatapoint.as_of",
        lazy="selectin",
    )

    __table_args__ = (
        sa.Index("ix_kpis_goal", "goal_id"),
        sa.Index("ix_kpis_objective", "objective_id"),
    )


class KPIDatapoint(UUIDMixin, Base):
    __tablename__ = "kpi_datapoints"

    kpi_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("kpis.id", ondelete="CASCADE"), nullable=False
    )
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(sa.Float, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)

    kpi: Mapped["KPI"] = relationship("KPI", back_populates="datapoints", lazy="joined")

    __table_args__ = (
        sa.UniqueConstraint("kpi_id", "as_of", name="uq_kpi_datapoint"),
        sa.Index("ix_kpi_datapoints_kpi", "kpi_id"),
    )


# -------------------------------
# Scorecards
# -------------------------------
class Scorecard(UUIDMixin, Base):
    __tablename__ = "scorecards"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    plan: Mapped["Plan"] = relationship("Plan", lazy="joined")
    kpi_links: Mapped[List["ScorecardKPI"]] = relationship(
        "ScorecardKPI",
        back_populates="scorecard",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    __table_args__ = (
        sa.Index("ix_scorecards_plan", "plan_id"),
    )


class ScorecardKPI(Base):
    __tablename__ = "scorecard_kpis"

    scorecard_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("scorecards.id", ondelete="CASCADE"), primary_key=True
    )
    kpi_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("kpis.id", ondelete="CASCADE"), primary_key=True
    )
    display_order: Mapped[Optional[int]] = mapped_column(Integer)

    scorecard: Mapped["Scorecard"] = relationship("Scorecard", back_populates="kpi_links", lazy="joined")
    kpi: Mapped["KPI"] = relationship("KPI", lazy="joined")


# -------------------------------
# Plan assignment / alignment / filters
# -------------------------------
class PlanAssignment(Base):
    __tablename__ = "plan_assignments"

    entity_type: Mapped[str] = mapped_column(String(50), primary_key=True)  # e.g., 'plan' | 'goal' | 'objective'
    entity_id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True)
    assignee_type: Mapped[str] = mapped_column(String(20), primary_key=True)  # user|group|role
    assignee_id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True)


class PlanAlignment(UUIDMixin, Base):
    __tablename__ = "plan_alignments"

    agenda_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("agenda_items.id", ondelete="SET NULL")
    )
    policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("policies.id", ondelete="SET NULL")
    )
    objective_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("objectives.id", ondelete="SET NULL")
    )
    note: Mapped[Optional[str]] = mapped_column(Text)

    agenda_item: Mapped[Optional["AgendaItem"]] = relationship("AgendaItem", lazy="joined")  # type: ignore[name-defined]
    policy: Mapped[Optional["Policy"]] = relationship("Policy", lazy="joined")              # type: ignore[name-defined]
    objective: Mapped[Optional["Objective"]] = relationship("Objective", lazy="joined")


class PlanFilter(UUIDMixin, Base):
    __tablename__ = "plan_filters"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    criteria: Mapped[Optional[dict]] = mapped_column(JSONB())

    plan: Mapped["Plan"] = relationship("Plan", lazy="joined")

    __table_args__ = (
        sa.Index("ix_plan_filters_plan", "plan_id"),
    )


class PlanSearchIndex(Base):
    __tablename__ = "plan_search_index"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True
    )
    ts: Mapped[Optional[str]] = mapped_column(TSVectorType())

    plan: Mapped["Plan"] = relationship("Plan", back_populates="search_index", lazy="joined")

    __table_args__ = (
        sa.Index("ix_plan_search_gin", "ts", postgresql_using="gin"),
    )
