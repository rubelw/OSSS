# src/OSSS/db/models/cmms_iwms.py
from __future__ import annotations

from typing import Optional, List

from sqlalchemy import (
    Column, String, Integer, Numeric, Boolean, Date, Text,
    ForeignKey, TIMESTAMP, func, UniqueConstraint, text
)
from sqlalchemy.orm import relationship, Mapped

from .base import Base, GUID, UUIDMixin, JSONB


# Helpers -------------------------------------------------------------
def ts_cols():
    return (
        Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
        Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
    )


# IWMS: Facilities / Space -------------------------------------------

class Facility(UUIDMixin, Base):
    __tablename__ = "facilities"

    school_id = Column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    code = Column(String(64), unique=True)
    address = Column(JSONB, nullable=True)
    attributes = Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    buildings = relationship("Building", back_populates="facility", cascade="all, delete-orphan")


class Building(UUIDMixin, Base):
    __tablename__ = "buildings"

    facility_id = Column(GUID(), ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    code = Column(String(64), unique=True)
    year_built = Column(Integer)
    floors_count = Column(Integer)
    gross_sqft = Column(Numeric(12, 2))
    use_type = Column(String(64))
    address = Column(JSONB, nullable=True)
    attributes = Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    facility = relationship("Facility", back_populates="buildings")
    floors = relationship("Floor", back_populates="building", cascade="all, delete-orphan")
    spaces = relationship("Space", back_populates="building", cascade="all, delete-orphan")


class Floor(UUIDMixin, Base):
    __tablename__ = "floors"

    building_id = Column(GUID(), ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False)
    level_code = Column(String(32), nullable=False)  # e.g., B1, 1, 2
    name = Column(String(128))
    created_at, updated_at = ts_cols()

    building = relationship("Building", back_populates="floors")
    spaces = relationship("Space", back_populates="floor")


class Space(UUIDMixin, Base):
    __tablename__ = "spaces"
    __table_args__ = (UniqueConstraint("building_id", "code", name="uq_spaces_building_code"),)

    building_id = Column(GUID(), ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False)
    floor_id = Column(GUID(), ForeignKey("floors.id", ondelete="SET NULL"), nullable=True)
    code = Column(String(64), nullable=False)  # room number
    name = Column(String(255))
    space_type = Column(String(64))
    area_sqft = Column(Numeric(12, 2))
    capacity = Column(Integer)
    attributes = Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    building = relationship("Building", back_populates="spaces")
    floor = relationship("Floor", back_populates="spaces")
    assets = relationship("Asset", back_populates="space")


# CMMS: Vendors / Parts / Inventory / Assets -------------------------

class Vendor(UUIDMixin, Base):
    __tablename__ = "vendors"

    name = Column(String(255), nullable=False, unique=True)
    contact = Column(JSONB, nullable=True)
    active = Column(Boolean, nullable=False, server_default=text("true"))
    notes = Column(Text)
    created_at, updated_at = ts_cols()

    warranties = relationship("Warranty", back_populates="vendor")


class Part(UUIDMixin, Base):
    __tablename__ = "parts"

    sku = Column(String(128), unique=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    unit_cost = Column(Numeric(12, 2))
    uom = Column(String(32))
    attributes = Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    locations = relationship("PartLocation", back_populates="part")
    work_order_parts = relationship("WorkOrderPart", back_populates="part")
    asset_parts = relationship("AssetPart", back_populates="part")


class PartLocation(UUIDMixin, Base):
    __tablename__ = "part_locations"

    part_id = Column(GUID(), ForeignKey("parts.id", ondelete="CASCADE"), nullable=False)
    building_id = Column(GUID(), ForeignKey("buildings.id", ondelete="SET NULL"))
    space_id = Column(GUID(), ForeignKey("spaces.id", ondelete="SET NULL"))
    location_code = Column(String(128))
    qty_on_hand = Column(Numeric(12, 2), nullable=False, server_default=text("0"))
    min_qty = Column(Numeric(12, 2))
    max_qty = Column(Numeric(12, 2))
    created_at, updated_at = ts_cols()

    part = relationship("Part", back_populates="locations")
    building = relationship("Building")
    space = relationship("Space")


class Asset(UUIDMixin, Base):
    __tablename__ = "assets"

    building_id = Column(GUID(), ForeignKey("buildings.id", ondelete="SET NULL"))
    space_id    = Column(GUID(), ForeignKey("spaces.id",    ondelete="SET NULL"))
    parent_asset_id = Column(GUID(), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)

    tag = Column(String(128), nullable=False, unique=True)
    serial_no = Column(String(128))
    manufacturer = Column(String(255))
    model = Column(String(255))
    category = Column(String(64))
    status = Column(String(32))
    install_date = Column(Date)
    warranty_expires_at = Column(Date)
    expected_life_months = Column(Integer)
    attributes = Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    building = relationship("Building")
    space    = relationship("Space", back_populates="assets")

    # self-referential: parent/children
    parent: Mapped[Optional["Asset"]] = relationship(
        "Asset",
        remote_side=lambda: [Asset.id],
        back_populates="children",
        foreign_keys=lambda: [Asset.parent_asset_id],
    )
    children: Mapped[List["Asset"]] = relationship(
        "Asset",
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys=lambda: [Asset.parent_asset_id],
    )

    parts              = relationship("AssetPart", back_populates="asset")
    meters             = relationship("Meter", back_populates="asset")
    pm_plans           = relationship("PMPlan", back_populates="asset")
    warranties         = relationship("Warranty", back_populates="asset")
    compliance_records = relationship("ComplianceRecord", back_populates="asset")
    work_orders        = relationship(
        "WorkOrder",
        back_populates="asset",
        foreign_keys=lambda: [WorkOrder.asset_id],
    )


class AssetPart(Base):
    __tablename__ = "asset_parts"

    asset_id = Column(GUID(), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)
    part_id = Column(GUID(), ForeignKey("parts.id", ondelete="CASCADE"), primary_key=True)
    qty = Column(Numeric(12, 2), nullable=False, server_default=text("1"))
    created_at, updated_at = ts_cols()

    asset = relationship("Asset", back_populates="parts")
    part = relationship("Part", back_populates="asset_parts")


class Meter(UUIDMixin, Base):
    __tablename__ = "meters"

    asset_id = Column(GUID(), ForeignKey("assets.id", ondelete="CASCADE"))
    building_id = Column(GUID(), ForeignKey("buildings.id", ondelete="CASCADE"))
    name = Column(String(255), nullable=False)
    meter_type = Column(String(64))
    uom = Column(String(32))
    last_read_value = Column(Numeric(18, 6))
    last_read_at = Column(TIMESTAMP(timezone=True))
    attributes = Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    asset = relationship("Asset", back_populates="meters")
    building = relationship("Building")


# Work Management -----------------------------------------------------

class MaintenanceRequest(UUIDMixin, Base):
    __tablename__ = "maintenance_requests"

    school_id  = Column(GUID(), ForeignKey("schools.id",   ondelete="SET NULL"))
    building_id= Column(GUID(), ForeignKey("buildings.id", ondelete="SET NULL"))
    space_id   = Column(GUID(), ForeignKey("spaces.id",    ondelete="SET NULL"))
    asset_id   = Column(GUID(), ForeignKey("assets.id",    ondelete="SET NULL"))
    submitted_by_user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    status = Column(String(32), nullable=False, server_default=text("'new'"))
    priority = Column(String(16))
    summary = Column(String(255), nullable=False)
    description = Column(Text)

    # legacy pointer (kept for compatibility)
    converted_work_order_id = Column(GUID(), ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True)

    attributes = Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    # canonical 1:1 link via WorkOrder.request_id
    work_order: Mapped[Optional["WorkOrder"]] = relationship(
        "WorkOrder",
        primaryjoin="MaintenanceRequest.id == foreign(WorkOrder.request_id)",
        back_populates="request",
        uselist=False,
    )

    # read-only convenience to legacy column
    converted_work_order: Mapped[Optional["WorkOrder"]] = relationship(
        "WorkOrder",
        primaryjoin="MaintenanceRequest.converted_work_order_id == WorkOrder.id",
        viewonly=True,
        uselist=False,
    )


class WorkOrder(UUIDMixin, Base):
    __tablename__ = "work_orders"

    school_id  = Column(GUID(), ForeignKey("schools.id",   ondelete="SET NULL"))
    building_id= Column(GUID(), ForeignKey("buildings.id", ondelete="SET NULL"))
    space_id   = Column(GUID(), ForeignKey("spaces.id",    ondelete="SET NULL"))
    asset_id   = Column(GUID(), ForeignKey("assets.id",    ondelete="SET NULL"))

    # canonical pointer back to request
    request_id = Column(GUID(), ForeignKey("maintenance_requests.id", ondelete="SET NULL"),
                        unique=True, nullable=True)

    status = Column(String(32), nullable=False, server_default=text("'open'"))
    priority = Column(String(16))
    category = Column(String(64))
    summary = Column(String(255), nullable=False)
    description = Column(Text)
    requested_due_at   = Column(TIMESTAMP(timezone=True))
    scheduled_start_at = Column(TIMESTAMP(timezone=True))
    scheduled_end_at   = Column(TIMESTAMP(timezone=True))
    completed_at       = Column(TIMESTAMP(timezone=True))
    assigned_to_user_id= Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    materials_cost = Column(Numeric(12, 2))
    labor_cost     = Column(Numeric(12, 2))
    other_cost     = Column(Numeric(12, 2))
    attributes = Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    request: Mapped[Optional["MaintenanceRequest"]] = relationship(
        "MaintenanceRequest",
        back_populates="work_order",
        foreign_keys=[request_id],
        uselist=False,
    )

    asset = relationship(
        "Asset",
        back_populates="work_orders",
        foreign_keys=[asset_id],
    )

    tasks      = relationship("WorkOrderTask", back_populates="work_order", cascade="all, delete-orphan")
    time_logs  = relationship("WorkOrderTimeLog", back_populates="work_order", cascade="all, delete-orphan")
    parts_used = relationship("WorkOrderPart",  back_populates="work_order", cascade="all, delete-orphan")

    # optional view of “converted from” via MR.converted_work_order_id (no back_populates)
    converted_from_request: Mapped[Optional["MaintenanceRequest"]] = relationship(
        "MaintenanceRequest",
        primaryjoin="WorkOrder.id == foreign(MaintenanceRequest.converted_work_order_id)",
        viewonly=True,
        uselist=False,
    )


class WorkOrderTask(UUIDMixin, Base):
    __tablename__ = "work_order_tasks"

    work_order_id = Column(GUID(), ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False)
    seq = Column(Integer, nullable=False, server_default=text("1"))
    title = Column(String(255), nullable=False)
    is_mandatory = Column(Boolean, nullable=False, server_default=text("false"))
    status = Column(String(32))
    completed_at = Column(TIMESTAMP(timezone=True))
    notes = Column(Text)
    created_at, updated_at = ts_cols()

    work_order = relationship("WorkOrder", back_populates="tasks")


class WorkOrderTimeLog(UUIDMixin, Base):
    __tablename__ = "work_order_time_logs"

    work_order_id = Column(GUID(), ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    started_at = Column(TIMESTAMP(timezone=True))
    ended_at = Column(TIMESTAMP(timezone=True))
    hours = Column(Numeric(10, 2))
    hourly_rate = Column(Numeric(12, 2))
    cost = Column(Numeric(12, 2))
    notes = Column(Text)
    created_at, updated_at = ts_cols()

    work_order = relationship("WorkOrder", back_populates="time_logs")


class WorkOrderPart(UUIDMixin, Base):
    __tablename__ = "work_order_parts"

    work_order_id = Column(GUID(), ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False)
    part_id = Column(GUID(), ForeignKey("parts.id", ondelete="SET NULL"))
    qty = Column(Numeric(12, 2), nullable=False, server_default=text("1"))
    unit_cost = Column(Numeric(12, 2))
    extended_cost = Column(Numeric(12, 2))
    notes = Column(Text)
    created_at, updated_at = ts_cols()

    work_order = relationship("WorkOrder", back_populates="parts_used")
    part = relationship("Part", back_populates="work_order_parts")


# Preventive Maintenance / Compliance --------------------------------

class PMPlan(UUIDMixin, Base):
    __tablename__ = "pm_plans"

    asset_id = Column(GUID(), ForeignKey("assets.id", ondelete="CASCADE"))
    building_id = Column(GUID(), ForeignKey("buildings.id", ondelete="CASCADE"))
    name = Column(String(255), nullable=False)
    frequency = Column(String(64))
    next_due_at = Column(TIMESTAMP(timezone=True))
    last_completed_at = Column(TIMESTAMP(timezone=True))
    active = Column(Boolean, nullable=False, server_default=text("true"))
    procedure = Column(JSONB, nullable=True)
    attributes = Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    asset = relationship("Asset", back_populates="pm_plans")
    building = relationship("Building")
    generators = relationship("PMWorkGenerator", back_populates="plan", cascade="all, delete-orphan")


class PMWorkGenerator(UUIDMixin, Base):
    __tablename__ = "pm_work_generators"

    pm_plan_id = Column(GUID(), ForeignKey("pm_plans.id", ondelete="CASCADE"), nullable=False)
    last_generated_at = Column(TIMESTAMP(timezone=True))
    lookahead_days = Column(Integer)
    attributes = Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    plan = relationship("PMPlan", back_populates="generators")


class Warranty(UUIDMixin, Base):
    __tablename__ = "warranties"

    asset_id = Column(GUID(), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    vendor_id = Column(GUID(), ForeignKey("vendors.id", ondelete="SET NULL"))
    policy_no = Column(String(128))
    start_date = Column(Date)
    end_date = Column(Date)
    terms = Column(Text)
    attributes = Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    asset = relationship("Asset", back_populates="warranties")
    vendor = relationship("Vendor", back_populates="warranties")


class ComplianceRecord(UUIDMixin, Base):
    __tablename__ = "compliance_records"

    building_id = Column(GUID(), ForeignKey("buildings.id", ondelete="SET NULL"))
    asset_id = Column(GUID(), ForeignKey("assets.id", ondelete="SET NULL"))
    record_type = Column(String(64), nullable=False)
    authority = Column(String(255))
    identifier = Column(String(128))
    issued_at = Column(Date)
    expires_at = Column(Date)
    documents = Column(JSONB, nullable=True)
    attributes = Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    building = relationship("Building")
    asset = relationship("Asset", back_populates="compliance_records")


# IWMS: Reservations / Leases / Projects / Moves ---------------------

class SpaceReservation(UUIDMixin, Base):
    __tablename__ = "space_reservations"

    space_id = Column(GUID(), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False)
    booked_by_user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    start_at = Column(TIMESTAMP(timezone=True), nullable=False)
    end_at = Column(TIMESTAMP(timezone=True), nullable=False)
    purpose = Column(String(255))
    status = Column(String(32), nullable=False, server_default=text("'booked'"))
    setup = Column(JSONB, nullable=True)
    attributes = Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    space = relationship("Space")


class Lease(UUIDMixin, Base):
    __tablename__ = "leases"

    building_id = Column(GUID(), ForeignKey("buildings.id", ondelete="SET NULL"))
    landlord = Column(String(255))
    tenant = Column(String(255))
    start_date = Column(Date)
    end_date = Column(Date)
    base_rent = Column(Numeric(14, 2))
    rent_schedule = Column(JSONB, nullable=True)
    options = Column(JSONB, nullable=True)
    documents = Column(JSONB, nullable=True)
    attributes = Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    building = relationship("Building")


class Project(UUIDMixin, Base):
    __tablename__ = "projects"

    school_id = Column(GUID(), ForeignKey("schools.id", ondelete="SET NULL"))
    name = Column(String(255), nullable=False)
    project_type = Column(String(32))
    status = Column(String(32))
    start_date = Column(Date)
    end_date = Column(Date)
    budget = Column(Numeric(14, 2))
    description = Column(Text)
    attributes = Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    tasks = relationship("ProjectTask", back_populates="project", cascade="all, delete-orphan")


class ProjectTask(UUIDMixin, Base):
    __tablename__ = "project_tasks"

    project_id = Column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(32))
    start_date = Column(Date)
    end_date = Column(Date)
    percent_complete = Column(Numeric(5, 2))
    assignee_user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    attributes = Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    project = relationship("Project", back_populates="tasks")


class MoveOrder(UUIDMixin, Base):
    __tablename__ = "move_orders"

    project_id = Column(GUID(), ForeignKey("projects.id", ondelete="SET NULL"))
    person_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    from_space_id = Column(GUID(), ForeignKey("spaces.id", ondelete="SET NULL"))
    to_space_id = Column(GUID(), ForeignKey("spaces.id", ondelete="SET NULL"))
    move_date = Column(Date)
    status = Column(String(32))
    attributes = Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    project = relationship("Project")
    from_space = relationship("Space", foreign_keys=[from_space_id])
    to_space = relationship("Space", foreign_keys=[to_space_id])
