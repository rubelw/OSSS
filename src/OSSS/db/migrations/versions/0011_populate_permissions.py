from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from datetime import date, datetime



# Pull the shims from your app (preferred)
try:
    from app.models.base import GUID, JSONB, TSVectorType  # GUID/JSONB TypeDecorator; TSVectorType for PG tsvector
except Exception:
    import uuid
    from sqlalchemy.types import TypeDecorator, CHAR

    class GUID(TypeDecorator):
        impl = CHAR
        cache_ok = True
        def load_dialect_impl(self, dialect):
            if dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import UUID as PGUUID
                return dialect.type_descriptor(PGUUID(as_uuid=True))
            return dialect.type_descriptor(sa.CHAR(36))
        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(str(value))
            return str(value)
        def process_result_value(self, value, dialect):
            return None if value is None else uuid.UUID(value)

    try:
        from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
    except Exception:
        PGJSONB = None

    class JSONB(TypeDecorator):
        impl = sa.JSON
        cache_ok = True
        def load_dialect_impl(self, dialect):
            if dialect.name == "postgresql" and PGJSONB is not None:
                return dialect.type_descriptor(PGJSONB())
            return dialect.type_descriptor(sa.JSON())

    try:
        from sqlalchemy.dialects.postgresql import TSVECTOR as PG_TSVECTOR
        class TSVectorType(PG_TSVECTOR):
            pass
    except Exception:
        class TSVectorType(sa.Text):
            pass

# --- Alembic identifiers ---
revision = "0011_populate_permissions"
down_revision = "0010_populate_roles"
branch_labels = None
depends_on = None

# ---- Timestamp helpers ----
def _timestamps():
    return (
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )



# ---------------------------
# Permission catalog
# ---------------------------
PERMISSIONS: list[tuple[str, str]] = [
    # ---------- SIS: Core Directory ----------
    ("sis.organizations.read", "View districts/organizations"),
    ("sis.schools.read", "View schools"),
    ("sis.schools.manage", "Create/update/delete schools"),
    ("sis.users.read", "View user accounts"),
    ("sis.users.manage", "Create/update/deactivate users"),
    ("sis.roles.read", "View roles & mappings"),
    ("sis.roles.manage", "Create/update roles; assign permissions"),
    # ---------- SIS: People & Contacts ----------
    ("sis.persons.read", "View person biographic data"),
    ("sis.persons.manage", "Manage person biographic data"),
    ("sis.students.read", "View student profiles"),
    ("sis.students.manage", "Create/update students; demographics"),
    ("sis.guardians.read", "View guardians"),
    ("sis.guardians.manage", "Manage guardians & relationships"),
    ("sis.contacts.read", "View contact endpoints (phone/email)"),
    ("sis.contacts.manage", "Create/update contact endpoints"),
    ("sis.addresses.read", "View addresses"),
    ("sis.addresses.manage", "Manage addresses"),
    # ---------- SIS: Enrollment ----------
    ("sis.enrollment.read", "View school/program enrollments"),
    ("sis.enrollment.manage", "Enroll/withdraw; manage programs"),
    ("sis.transfers.process", "Approve inbound/outbound transfers"),
    # ---------- SIS: Calendars, Terms, Schedules ----------
    ("sis.terms.read", "View academic terms & grading periods"),
    ("sis.terms.manage", "Manage terms & grading periods"),
    ("sis.calendars.read", "View calendars & bell schedules"),
    ("sis.calendars.manage", "Manage calendars, days, bells, periods"),
    ("sis.scheduling.view", "View courses/sections/timetables"),
    ("sis.scheduling.manage", "Build master schedule; manage sections"),
    ("sis.requests.manage", "Manage student course requests"),
    # ---------- SIS: Classes, Gradebook, Grades ----------
    ("sis.sections.read", "View course sections & rosters"),
    ("sis.assignments.manage_own", "Create/manage assignments (own sections)"),
    ("sis.gradebook.edit_own", "Enter/modify scores (own sections)"),
    ("sis.gradebook.override", "Override grades beyond standard rules"),
    ("sis.final_grades.submit_own", "Submit final grades (own sections)"),
    ("sis.final_grades.manage_all", "Manage final grades for any section"),
    ("sis.grade_scales.manage", "Create/modify grade scales & bands"),
    # ---------- SIS: Attendance ----------
    ("sis.attendance.view", "View attendance (daily/period)"),
    ("sis.attendance.submit_own", "Take attendance for own sections"),
    ("sis.attendance.manage", "Office—edit/clear/override attendance"),
    ("sis.attendance.codes.manage", "Manage attendance codes"),
    # ---------- SIS: Behavior & Discipline ----------
    ("sis.incidents.view", "View behavior incidents"),
    ("sis.incidents.create", "Create behavior incidents"),
    ("sis.incidents.manage", "Edit incidents; assign consequences"),
    ("sis.behavior.codes.manage", "Manage behavior/consequence codes"),
    # ---------- SIS: Health ----------
    ("sis.health.view", "View health profiles (min. PHI)"),
    ("sis.health.manage", "Manage immunizations, meds, nurse visits"),
    # ---------- SIS: Special Services ----------
    ("sis.sped.view", "View IEP/504/ELL/accommodations"),
    ("sis.sped.manage", "Create/update IEP/504/ELL records"),
    # ---------- SIS: Fees, Meals, Library, Transport ----------
    ("sis.fees.manage", "Create fees, invoices, payments, waivers"),
    ("sis.meals.view", "View meal accounts & eligibility"),
    ("sis.meals.manage", "Post transactions; set eligibility"),
    ("sis.library.manage", "Manage items, checkouts, holds, fines"),
    ("sis.transport.manage", "Manage routes, stops, assignments"),
    # ---------- SIS: Assessments & Reports ----------
    ("sis.tests.manage", "Manage standardized tests & results"),
    ("sis.reports.view", "Run standard reports & exports"),
    ("sis.analytics.view", "View analytics & dashboards"),
    ("sis.imports.run", "Run SIS import/ETL jobs"),
    # ---------- SIS: Settings & Search ----------
    ("sis.settings.manage", "Global SIS settings"),
    ("sis.search.index.manage", "Manage search indices"),
    ("sis.files.upload", "Upload files to records"),
    # ---------- CIC: Communications / Governance / Policy ----------
    ("cic.channels.manage", "Create channels; manage audiences"),
    ("cic.posts.create", "Create posts/messages"),
    ("cic.posts.edit", "Edit posts/messages"),
    ("cic.posts.publish", "Publish/schedule posts"),
    ("cic.pages.manage", "Manage web pages"),
    ("cic.subscriptions.manage", "Manage subscriptions & deliveries"),
    ("cic.alerts.send", "Send mass/emergency alerts"),
    ("cic.meetings.manage", "Create meetings; agendas; minutes"),
    ("cic.policies.manage", "Create policies; versions; approvals"),
    ("cic.policies.publish", "Publish policies & updates"),
    # ---------- CMMS: Facilities / Maintenance ----------
    ("cmms.assets.read", "View assets & locations"),
    ("cmms.assets.manage", "Create/update assets & locations"),
    ("cmms.work_orders.create", "Create work orders/requests"),
    ("cmms.work_orders.assign", "Assign work orders"),
    ("cmms.work_orders.update", "Add notes/time; change status"),
    ("cmms.work_orders.close", "Close/complete work orders"),
    ("cmms.work_orders.approve", "Approve WOs & purchases"),
    ("cmms.pm.manage", "Manage preventive maintenance plans"),
    ("cmms.inventory.read", "View inventory"),
    ("cmms.inventory.manage", "Receive/issue/adjust inventory"),
    ("cmms.vendors.manage", "Manage vendors & contracts"),
    ("cmms.reports.view", "View CMMS reports"),
    ("cmms.settings.manage", "CMMS configuration"),
]

# ---------------------------
# Role -> permissions mapping
# (must match role names already seeded)
# ---------------------------
ROLE_PERMS: dict[str, list[str]] = {
    "District Administrator": [
        "sis.organizations.read", "sis.schools.manage", "sis.users.manage", "sis.roles.manage",
        "sis.persons.manage", "sis.students.manage", "sis.guardians.manage", "sis.contacts.manage",
        "sis.addresses.manage", "sis.enrollment.manage", "sis.transfers.process", "sis.terms.manage",
        "sis.calendars.manage", "sis.scheduling.manage", "sis.sections.read", "sis.assignments.manage_own",
        "sis.gradebook.override", "sis.final_grades.manage_all", "sis.attendance.manage",
        "sis.attendance.codes.manage", "sis.incidents.manage", "sis.behavior.codes.manage",
        "sis.health.manage", "sis.sped.manage", "sis.fees.manage", "sis.meals.manage",
        "sis.library.manage", "sis.transport.manage", "sis.tests.manage", "sis.reports.view",
        "sis.analytics.view", "sis.imports.run", "sis.settings.manage", "sis.search.index.manage",
        "sis.files.upload",
        "cic.channels.manage", "cic.posts.create", "cic.posts.edit", "cic.posts.publish",
        "cic.pages.manage", "cic.subscriptions.manage", "cic.alerts.send", "cic.meetings.manage",
        "cic.policies.manage", "cic.policies.publish",
        "cmms.assets.manage", "cmms.work_orders.approve", "cmms.work_orders.assign",
        "cmms.work_orders.close", "cmms.pm.manage", "cmms.inventory.manage", "cmms.vendors.manage",
        "cmms.reports.view", "cmms.settings.manage",
    ],
    "IT Administrator": [
        "sis.users.manage", "sis.roles.manage", "sis.settings.manage", "sis.search.index.manage",
        "sis.files.upload", "cic.channels.manage", "cic.pages.manage", "cmms.settings.manage",
        "cmms.assets.manage",
    ],
    "School Administrator (Principal/AP)": [
        "sis.schools.read", "sis.persons.read", "sis.students.manage", "sis.guardians.manage",
        "sis.enrollment.manage", "sis.terms.read", "sis.calendars.manage", "sis.scheduling.manage",
        "sis.sections.read", "sis.gradebook.override", "sis.final_grades.manage_all",
        "sis.attendance.manage", "sis.incidents.manage", "sis.health.view", "sis.sped.view",
        "sis.fees.manage", "sis.meals.view", "sis.reports.view", "sis.files.upload",
        "cic.posts.create", "cic.posts.publish", "cic.meetings.manage", "cic.policies.manage",
        "cmms.work_orders.approve", "cmms.work_orders.assign", "cmms.reports.view",
    ],
    "Registrar": [
        "sis.persons.manage", "sis.students.manage", "sis.guardians.manage", "sis.contacts.manage",
        "sis.addresses.manage", "sis.enrollment.manage", "sis.transfers.process", "sis.reports.view",
        "sis.files.upload",
    ],
    "Counselor": [
        "sis.students.read", "sis.enrollment.read", "sis.sections.read", "sis.requests.manage",
        "sis.gradebook.edit_own", "sis.final_grades.submit_own", "sis.attendance.view",
        "sis.incidents.view", "sis.sped.view", "sis.health.view", "sis.reports.view",
    ],
    "Attendance Clerk": [
        "sis.attendance.manage", "sis.attendance.codes.manage", "sis.students.read", "sis.sections.read",
        "sis.reports.view",
    ],
    "Discipline Dean": [
        "sis.incidents.manage", "sis.behavior.codes.manage", "sis.students.read", "sis.attendance.view",
        "sis.reports.view",
    ],
    "Special Education Coordinator": [
        "sis.sped.manage", "sis.students.read", "sis.sections.read", "sis.attendance.view",
        "sis.final_grades.manage_all", "sis.reports.view", "sis.files.upload",
    ],
    "School Nurse": [
        "sis.health.manage", "sis.students.read", "sis.attendance.view", "sis.reports.view",
    ],
    "Teacher": [
        "sis.sections.read", "sis.students.read", "sis.attendance.submit_own", "sis.assignments.manage_own",
        "sis.gradebook.edit_own", "sis.final_grades.submit_own", "sis.reports.view",
        "cmms.work_orders.create",
    ],
    "Substitute Teacher": [
        "sis.sections.read", "sis.students.read", "sis.attendance.submit_own",
    ],
    "Librarian / Media Specialist": [
        "sis.library.manage", "sis.students.read", "sis.reports.view",
    ],
    "Food Service Manager": [
        "sis.meals.manage", "sis.students.read", "sis.reports.view",
    ],
    "Transportation Coordinator": [
        "sis.transport.manage", "sis.students.read", "sis.reports.view",
    ],
    "Communications Director": [
        "cic.channels.manage", "cic.posts.create", "cic.posts.edit", "cic.posts.publish",
        "cic.pages.manage", "cic.subscriptions.manage", "cic.alerts.send", "cic.meetings.manage",
        "cic.policies.manage", "cic.policies.publish", "sis.reports.view",
    ],
    "Board Member": [
        "cic.meetings.manage", "cic.policies.manage", "sis.reports.view",
    ],
    "Parent / Guardian (Portal)": [
        "sis.students.read", "sis.attendance.view", "sis.reports.view", "sis.meals.view", "sis.fees.manage",
    ],
    "Student (Portal)": [
        "sis.students.read", "sis.sections.read", "sis.attendance.view", "sis.reports.view",
    ],
    "Facilities Manager": [
        "cmms.assets.manage", "cmms.work_orders.assign", "cmms.work_orders.update",
        "cmms.work_orders.close", "cmms.work_orders.approve", "cmms.pm.manage",
        "cmms.inventory.manage", "cmms.vendors.manage", "cmms.reports.view",
    ],
    "Maintenance Technician": [
        "cmms.assets.read", "cmms.work_orders.update", "cmms.work_orders.close", "cmms.inventory.read",
    ],
    "Custodian": [
        "cmms.assets.read", "cmms.work_orders.update", "cmms.inventory.read",
    ],
    "Safety / Security Officer": [
        "cic.alerts.send", "cic.posts.create", "cic.posts.publish", "sis.incidents.manage", "sis.reports.view",
    ],
    "Business / Finance Manager": [
        "sis.fees.manage", "sis.meals.view", "sis.reports.view", "cmms.reports.view",
    ],
}


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    is_pg = dialect == "postgresql"

    # --- 1) Upsert permissions by (code) ---
    if is_pg:
        insert_perm = sa.text("""
            INSERT INTO permissions (code, description)
            VALUES (:code, :desc)
            ON CONFLICT (code) DO UPDATE
            SET description = EXCLUDED.description
        """)
    else:
        # SQLite
        insert_perm = sa.text("""
            INSERT OR IGNORE INTO permissions (code, description)
            VALUES (:code, :desc)
        """)
        update_desc = sa.text("""
            UPDATE permissions SET description = :desc
            WHERE code = :code
        """)

    for code, desc in PERMISSIONS:
        bind.execute(insert_perm, {"code": code, "desc": desc})
        if not is_pg:
            bind.execute(update_desc, {"code": code, "desc": desc})

    # Build permission_id map
    perm_codes = [p[0] for p in PERMISSIONS]
    rows = bind.execute(
        sa.text("SELECT id, code FROM permissions WHERE code = ANY(:codes)")
        if is_pg else
        sa.text("SELECT id, code FROM permissions")
    , {"codes": perm_codes} if is_pg else {}
    ).mappings().all()
    perm_id_by_code = {r["code"]: r["id"] for r in rows if r["code"] in perm_codes}

    # Build role_id map for known roles
    role_names = list(ROLE_PERMS.keys())
    rows = bind.execute(
        sa.text("SELECT id, name FROM roles WHERE name = ANY(:names)")
        if is_pg else
        sa.text("SELECT id, name FROM roles")
    , {"names": role_names} if is_pg else {}
    ).mappings().all()
    role_id_by_name = {r["name"]: r["id"] for r in rows if r["name"] in role_names}

    # --- 2) Link roles to permissions (ignore missing roles gracefully) ---
    if is_pg:
        insert_rp = sa.text("""
            INSERT INTO role_permissions (role_id, permission_id, created_at, updated_at)
            VALUES (:rid, :pid, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT DO NOTHING
        """)
    else:
        insert_rp = sa.text("""
            INSERT OR IGNORE INTO role_permissions (role_id, permission_id, created_at, updated_at)
            VALUES (:rid, :pid, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """)

    for role_name, perm_list in ROLE_PERMS.items():
        rid = role_id_by_name.get(role_name)
        if not rid:
            # role not present in DB; skip quietly
            continue
        for code in perm_list:
            pid = perm_id_by_code.get(code)
            if not pid:
                continue
            bind.execute(insert_rp, {"rid": rid, "pid": pid})


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # Determine permission ids we seeded
    perm_codes = [p[0] for p in PERMISSIONS]
    sel = (
        sa.text("SELECT id FROM permissions WHERE code = ANY(:codes)")
        if is_pg else
        sa.text("SELECT id FROM permissions")
    )
    rows = bind.execute(sel, {"codes": perm_codes} if is_pg else {}).mappings().all()
    perm_ids = [r["id"] for r in rows if r.get("id")]

    # 1) Remove role_permission links for these permissions
    if perm_ids:
        bind.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = ANY(:pids)")
            if is_pg else
            sa.text("DELETE FROM role_permissions WHERE permission_id IN (%s)" % (
                ",".join(["?"] * len(perm_ids))
            )),
            {"pids": perm_ids} if is_pg else perm_ids
        )

    # 2) Remove the permissions we added
    if is_pg:
        bind.execute(sa.text("DELETE FROM permissions WHERE code = ANY(:codes)"), {"codes": perm_codes})
    else:
        # SQLite
        qmarks = ",".join(["?"] * len(perm_codes))
        bind.execute(sa.text(f"DELETE FROM permissions WHERE code IN ({qmarks})"), perm_codes)

# ---------------------------
# Permission catalog
# ---------------------------
PERMISSIONS: list[tuple[str, str]] = [
    # ---------- SIS: Core Directory ----------
    ("sis.organizations.read", "View districts/organizations"),
    ("sis.schools.read", "View schools"),
    ("sis.schools.manage", "Create/update/delete schools"),
    ("sis.users.read", "View user accounts"),
    ("sis.users.manage", "Create/update/deactivate users"),
    ("sis.roles.read", "View roles & mappings"),
    ("sis.roles.manage", "Create/update roles; assign permissions"),
    # ---------- SIS: People & Contacts ----------
    ("sis.persons.read", "View person biographic data"),
    ("sis.persons.manage", "Manage person biographic data"),
    ("sis.students.read", "View student profiles"),
    ("sis.students.manage", "Create/update students; demographics"),
    ("sis.guardians.read", "View guardians"),
    ("sis.guardians.manage", "Manage guardians & relationships"),
    ("sis.contacts.read", "View contact endpoints (phone/email)"),
    ("sis.contacts.manage", "Create/update contact endpoints"),
    ("sis.addresses.read", "View addresses"),
    ("sis.addresses.manage", "Manage addresses"),
    # ---------- SIS: Enrollment ----------
    ("sis.enrollment.read", "View school/program enrollments"),
    ("sis.enrollment.manage", "Enroll/withdraw; manage programs"),
    ("sis.transfers.process", "Approve inbound/outbound transfers"),
    # ---------- SIS: Calendars, Terms, Schedules ----------
    ("sis.terms.read", "View academic terms & grading periods"),
    ("sis.terms.manage", "Manage terms & grading periods"),
    ("sis.calendars.read", "View calendars & bell schedules"),
    ("sis.calendars.manage", "Manage calendars, days, bells, periods"),
    ("sis.scheduling.view", "View courses/sections/timetables"),
    ("sis.scheduling.manage", "Build master schedule; manage sections"),
    ("sis.requests.manage", "Manage student course requests"),
    # ---------- SIS: Classes, Gradebook, Grades ----------
    ("sis.sections.read", "View course sections & rosters"),
    ("sis.assignments.manage_own", "Create/manage assignments (own sections)"),
    ("sis.gradebook.edit_own", "Enter/modify scores (own sections)"),
    ("sis.gradebook.override", "Override grades beyond standard rules"),
    ("sis.final_grades.submit_own", "Submit final grades (own sections)"),
    ("sis.final_grades.manage_all", "Manage final grades for any section"),
    ("sis.grade_scales.manage", "Create/modify grade scales & bands"),
    # ---------- SIS: Attendance ----------
    ("sis.attendance.view", "View attendance (daily/period)"),
    ("sis.attendance.submit_own", "Take attendance for own sections"),
    ("sis.attendance.manage", "Office—edit/clear/override attendance"),
    ("sis.attendance.codes.manage", "Manage attendance codes"),
    # ---------- SIS: Behavior & Discipline ----------
    ("sis.incidents.view", "View behavior incidents"),
    ("sis.incidents.create", "Create behavior incidents"),
    ("sis.incidents.manage", "Edit incidents; assign consequences"),
    ("sis.behavior.codes.manage", "Manage behavior/consequence codes"),
    # ---------- SIS: Health ----------
    ("sis.health.view", "View health profiles (min. PHI)"),
    ("sis.health.manage", "Manage immunizations, meds, nurse visits"),
    # ---------- SIS: Special Services ----------
    ("sis.sped.view", "View IEP/504/ELL/accommodations"),
    ("sis.sped.manage", "Create/update IEP/504/ELL records"),
    # ---------- SIS: Fees, Meals, Library, Transport ----------
    ("sis.fees.manage", "Create fees, invoices, payments, waivers"),
    ("sis.meals.view", "View meal accounts & eligibility"),
    ("sis.meals.manage", "Post transactions; set eligibility"),
    ("sis.library.manage", "Manage items, checkouts, holds, fines"),
    ("sis.transport.manage", "Manage routes, stops, assignments"),
    # ---------- SIS: Assessments & Reports ----------
    ("sis.tests.manage", "Manage standardized tests & results"),
    ("sis.reports.view", "Run standard reports & exports"),
    ("sis.analytics.view", "View analytics & dashboards"),
    ("sis.imports.run", "Run SIS import/ETL jobs"),
    # ---------- SIS: Settings & Search ----------
    ("sis.settings.manage", "Global SIS settings"),
    ("sis.search.index.manage", "Manage search indices"),
    ("sis.files.upload", "Upload files to records"),
    # ---------- CIC: Communications / Governance / Policy ----------
    ("cic.channels.manage", "Create channels; manage audiences"),
    ("cic.posts.create", "Create posts/messages"),
    ("cic.posts.edit", "Edit posts/messages"),
    ("cic.posts.publish", "Publish/schedule posts"),
    ("cic.pages.manage", "Manage web pages"),
    ("cic.subscriptions.manage", "Manage subscriptions & deliveries"),
    ("cic.alerts.send", "Send mass/emergency alerts"),
    ("cic.meetings.manage", "Create meetings; agendas; minutes"),
    ("cic.policies.manage", "Create policies; versions; approvals"),
    ("cic.policies.publish", "Publish policies & updates"),
    # ---------- CMMS: Facilities / Maintenance ----------
    ("cmms.assets.read", "View assets & locations"),
    ("cmms.assets.manage", "Create/update assets & locations"),
    ("cmms.work_orders.create", "Create work orders/requests"),
    ("cmms.work_orders.assign", "Assign work orders"),
    ("cmms.work_orders.update", "Add notes/time; change status"),
    ("cmms.work_orders.close", "Close/complete work orders"),
    ("cmms.work_orders.approve", "Approve WOs & purchases"),
    ("cmms.pm.manage", "Manage preventive maintenance plans"),
    ("cmms.inventory.read", "View inventory"),
    ("cmms.inventory.manage", "Receive/issue/adjust inventory"),
    ("cmms.vendors.manage", "Manage vendors & contracts"),
    ("cmms.reports.view", "View CMMS reports"),
    ("cmms.settings.manage", "CMMS configuration"),
]

# ---------------------------
# Role -> permissions mapping
# (must match role names already seeded)
# ---------------------------
ROLE_PERMS: dict[str, list[str]] = {
    "District Administrator": [
        "sis.organizations.read", "sis.schools.manage", "sis.users.manage", "sis.roles.manage",
        "sis.persons.manage", "sis.students.manage", "sis.guardians.manage", "sis.contacts.manage",
        "sis.addresses.manage", "sis.enrollment.manage", "sis.transfers.process", "sis.terms.manage",
        "sis.calendars.manage", "sis.scheduling.manage", "sis.sections.read", "sis.assignments.manage_own",
        "sis.gradebook.override", "sis.final_grades.manage_all", "sis.attendance.manage",
        "sis.attendance.codes.manage", "sis.incidents.manage", "sis.behavior.codes.manage",
        "sis.health.manage", "sis.sped.manage", "sis.fees.manage", "sis.meals.manage",
        "sis.library.manage", "sis.transport.manage", "sis.tests.manage", "sis.reports.view",
        "sis.analytics.view", "sis.imports.run", "sis.settings.manage", "sis.search.index.manage",
        "sis.files.upload",
        "cic.channels.manage", "cic.posts.create", "cic.posts.edit", "cic.posts.publish",
        "cic.pages.manage", "cic.subscriptions.manage", "cic.alerts.send", "cic.meetings.manage",
        "cic.policies.manage", "cic.policies.publish",
        "cmms.assets.manage", "cmms.work_orders.approve", "cmms.work_orders.assign",
        "cmms.work_orders.close", "cmms.pm.manage", "cmms.inventory.manage", "cmms.vendors.manage",
        "cmms.reports.view", "cmms.settings.manage",
    ],
    "IT Administrator": [
        "sis.users.manage", "sis.roles.manage", "sis.settings.manage", "sis.search.index.manage",
        "sis.files.upload", "cic.channels.manage", "cic.pages.manage", "cmms.settings.manage",
        "cmms.assets.manage",
    ],
    "School Administrator (Principal/AP)": [
        "sis.schools.read", "sis.persons.read", "sis.students.manage", "sis.guardians.manage",
        "sis.enrollment.manage", "sis.terms.read", "sis.calendars.manage", "sis.scheduling.manage",
        "sis.sections.read", "sis.gradebook.override", "sis.final_grades.manage_all",
        "sis.attendance.manage", "sis.incidents.manage", "sis.health.view", "sis.sped.view",
        "sis.fees.manage", "sis.meals.view", "sis.reports.view", "sis.files.upload",
        "cic.posts.create", "cic.posts.publish", "cic.meetings.manage", "cic.policies.manage",
        "cmms.work_orders.approve", "cmms.work_orders.assign", "cmms.reports.view",
    ],
    "Registrar": [
        "sis.persons.manage", "sis.students.manage", "sis.guardians.manage", "sis.contacts.manage",
        "sis.addresses.manage", "sis.enrollment.manage", "sis.transfers.process", "sis.reports.view",
        "sis.files.upload",
    ],
    "Counselor": [
        "sis.students.read", "sis.enrollment.read", "sis.sections.read", "sis.requests.manage",
        "sis.gradebook.edit_own", "sis.final_grades.submit_own", "sis.attendance.view",
        "sis.incidents.view", "sis.sped.view", "sis.health.view", "sis.reports.view",
    ],
    "Attendance Clerk": [
        "sis.attendance.manage", "sis.attendance.codes.manage", "sis.students.read", "sis.sections.read",
        "sis.reports.view",
    ],
    "Discipline Dean": [
        "sis.incidents.manage", "sis.behavior.codes.manage", "sis.students.read", "sis.attendance.view",
        "sis.reports.view",
    ],
    "Special Education Coordinator": [
        "sis.sped.manage", "sis.students.read", "sis.sections.read", "sis.attendance.view",
        "sis.final_grades.manage_all", "sis.reports.view", "sis.files.upload",
    ],
    "School Nurse": [
        "sis.health.manage", "sis.students.read", "sis.attendance.view", "sis.reports.view",
    ],
    "Teacher": [
        "sis.sections.read", "sis.students.read", "sis.attendance.submit_own", "sis.assignments.manage_own",
        "sis.gradebook.edit_own", "sis.final_grades.submit_own", "sis.reports.view",
        "cmms.work_orders.create",
    ],
    "Substitute Teacher": [
        "sis.sections.read", "sis.students.read", "sis.attendance.submit_own",
    ],
    "Librarian / Media Specialist": [
        "sis.library.manage", "sis.students.read", "sis.reports.view",
    ],
    "Food Service Manager": [
        "sis.meals.manage", "sis.students.read", "sis.reports.view",
    ],
    "Transportation Coordinator": [
        "sis.transport.manage", "sis.students.read", "sis.reports.view",
    ],
    "Communications Director": [
        "cic.channels.manage", "cic.posts.create", "cic.posts.edit", "cic.posts.publish",
        "cic.pages.manage", "cic.subscriptions.manage", "cic.alerts.send", "cic.meetings.manage",
        "cic.policies.manage", "cic.policies.publish", "sis.reports.view",
    ],
    "Board Member": [
        "cic.meetings.manage", "cic.policies.manage", "sis.reports.view",
    ],
    "Parent / Guardian (Portal)": [
        "sis.students.read", "sis.attendance.view", "sis.reports.view", "sis.meals.view", "sis.fees.manage",
    ],
    "Student (Portal)": [
        "sis.students.read", "sis.sections.read", "sis.attendance.view", "sis.reports.view",
    ],
    "Facilities Manager": [
        "cmms.assets.manage", "cmms.work_orders.assign", "cmms.work_orders.update",
        "cmms.work_orders.close", "cmms.work_orders.approve", "cmms.pm.manage",
        "cmms.inventory.manage", "cmms.vendors.manage", "cmms.reports.view",
    ],
    "Maintenance Technician": [
        "cmms.assets.read", "cmms.work_orders.update", "cmms.work_orders.close", "cmms.inventory.read",
    ],
    "Custodian": [
        "cmms.assets.read", "cmms.work_orders.update", "cmms.inventory.read",
    ],
    "Safety / Security Officer": [
        "cic.alerts.send", "cic.posts.create", "cic.posts.publish", "sis.incidents.manage", "sis.reports.view",
    ],
    "Business / Finance Manager": [
        "sis.fees.manage", "sis.meals.view", "sis.reports.view", "cmms.reports.view",
    ],
}


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    is_pg = dialect == "postgresql"

    # --- 1) Upsert permissions by (code) ---
    if is_pg:
        insert_perm = sa.text("""
            INSERT INTO permissions (code, description)
            VALUES (:code, :desc)
            ON CONFLICT (code) DO UPDATE
            SET description = EXCLUDED.description
        """)
    else:
        # SQLite
        insert_perm = sa.text("""
            INSERT OR IGNORE INTO permissions (code, description)
            VALUES (:code, :desc)
        """)
        update_desc = sa.text("""
            UPDATE permissions SET description = :desc
            WHERE code = :code
        """)

    for code, desc in PERMISSIONS:
        bind.execute(insert_perm, {"code": code, "desc": desc})
        if not is_pg:
            bind.execute(update_desc, {"code": code, "desc": desc})

    # Build permission_id map
    perm_codes = [p[0] for p in PERMISSIONS]
    rows = bind.execute(
        sa.text("SELECT id, code FROM permissions WHERE code = ANY(:codes)")
        if is_pg else
        sa.text("SELECT id, code FROM permissions")
    , {"codes": perm_codes} if is_pg else {}
    ).mappings().all()
    perm_id_by_code = {r["code"]: r["id"] for r in rows if r["code"] in perm_codes}

    # Build role_id map for known roles
    role_names = list(ROLE_PERMS.keys())
    rows = bind.execute(
        sa.text("SELECT id, name FROM roles WHERE name = ANY(:names)")
        if is_pg else
        sa.text("SELECT id, name FROM roles")
    , {"names": role_names} if is_pg else {}
    ).mappings().all()
    role_id_by_name = {r["name"]: r["id"] for r in rows if r["name"] in role_names}

    # --- 2) Link roles to permissions (ignore missing roles gracefully) ---
    if is_pg:
        insert_rp = sa.text("""
            INSERT INTO role_permissions (role_id, permission_id, created_at, updated_at)
            VALUES (:rid, :pid, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT DO NOTHING
        """)
    else:
        insert_rp = sa.text("""
            INSERT OR IGNORE INTO role_permissions (role_id, permission_id, created_at, updated_at)
            VALUES (:rid, :pid, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """)

    for role_name, perm_list in ROLE_PERMS.items():
        rid = role_id_by_name.get(role_name)
        if not rid:
            # role not present in DB; skip quietly
            continue
        for code in perm_list:
            pid = perm_id_by_code.get(code)
            if not pid:
                continue
            bind.execute(insert_rp, {"rid": rid, "pid": pid})


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # Determine permission ids we seeded
    perm_codes = [p[0] for p in PERMISSIONS]
    sel = (
        sa.text("SELECT id FROM permissions WHERE code = ANY(:codes)")
        if is_pg else
        sa.text("SELECT id FROM permissions")
    )
    rows = bind.execute(sel, {"codes": perm_codes} if is_pg else {}).mappings().all()
    perm_ids = [r["id"] for r in rows if r.get("id")]

    # 1) Remove role_permission links for these permissions
    if perm_ids:
        bind.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = ANY(:pids)")
            if is_pg else
            sa.text("DELETE FROM role_permissions WHERE permission_id IN (%s)" % (
                ",".join(["?"] * len(perm_ids))
            )),
            {"pids": perm_ids} if is_pg else perm_ids
        )

    # 2) Remove the permissions we added
    if is_pg:
        bind.execute(sa.text("DELETE FROM permissions WHERE code = ANY(:codes)"), {"codes": perm_codes})
    else:
        # SQLite
        qmarks = ",".join(["?"] * len(perm_codes))
        bind.execute(sa.text(f"DELETE FROM permissions WHERE code IN ({qmarks})"), perm_codes)