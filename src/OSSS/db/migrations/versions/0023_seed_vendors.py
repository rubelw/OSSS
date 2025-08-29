# versions/0023_create_seed_vendors.py
from __future__ import annotations

import random
import re
import uuid
from typing import List, Dict

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# --- Alembic identifiers
revision = "0023_create_seed_vendors"
down_revision = "0022_seed_hr_employees"
branch_labels = None
depends_on = None


def _slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    s = re.sub(r"-+", "-", s)
    return s or "vendor"


def upgrade():
    # Ensure gen_random_uuid() is available
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")



    # ----- Seed data (deterministic) -----
    rng = random.Random(42)

    brands = [
        "Atlas", "Summit", "Cedar", "Nimbus", "Aurora", "Pioneer", "Harbor",
        "Vertex", "Northstar", "Blue Ridge", "Oakstone", "Silverline",
        "Prime", "Prairie", "Riverview", "Crescent", "Westfield", "Redwood",
        "Evergreen", "Beacon", "Meridian", "Terrace", "Granite", "Skyline",
    ]
    sectors = [
        "Education", "Technology", "Services", "Facilities", "Foodservice",
        "Transportation", "Security", "Wellness", "Curriculum", "Assessment",
        "Athletics", "Communications", "Data Systems", "Cloud", "Networking",
        "Textbooks", "AV Media", "Janitorial", "Maintenance", "Consulting",
    ]
    suffixes = ["LLC", "Inc.", "Ltd.", "Group", "Co.", "Partners", "Systems", "Solutions"]

    first_names = [
        "Alex", "Jordan", "Taylor", "Riley", "Casey", "Drew", "Cameron", "Quinn",
        "Morgan", "Avery", "Hayden", "Parker", "Reese", "Rowan", "Emerson",
    ]
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
        "Wilson", "Anderson", "Thomas", "Taylor", "Moore",
    ]

    def make_vendor(i: int) -> Dict:
        name = f"{rng.choice(brands)} {rng.choice(sectors)} {rng.choice(suffixes)}"
        contact_first = rng.choice(first_names)
        contact_last = rng.choice(last_names)
        domain = _slug(name) + ".com"
        email = f"{contact_first.lower()}.{contact_last.lower()}@{domain}"
        phone = f"555-{rng.randint(200, 999):03d}-{rng.randint(1000, 9999):04d}"
        active = rng.random() > 0.12  # ~88% active
        notes = rng.choice([
            "Preferred vendor",
            "Onboarding complete",
            "Contract pending renewal",
            "RFP finalist last cycle",
            "Legacy integration; monitor SLAs",
            "Pilot in two schools",
            None,
        ])
        # deterministic id from name
        vid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"osss/vendor/{name}"))
        return {
            "id": vid,
            "name": name,
            "contact": {"name": f"{contact_first} {contact_last}", "email": email, "phone": phone},
            "active": active,
            "notes": notes,
        }

    seed_rows: List[Dict] = [make_vendor(i) for i in range(30)]

    # Insert (ON CONFLICT name DO NOTHING)
    conn = op.get_bind()
    insert_sql = sa.text("""
        INSERT INTO vendors (id, name, contact, active, notes)
        VALUES (:id, :name, :contact, :active, :notes)
        ON CONFLICT (name) DO NOTHING
    """).bindparams(
        sa.bindparam("id"),
        sa.bindparam("name"),
        sa.bindparam("contact", type_=JSONB),
        sa.bindparam("active"),
        sa.bindparam("notes"),
    )
    conn.execute(insert_sql, seed_rows)


def downgrade():
    # Drop everything (warranties that FK to vendors should be ON DELETE CASCADE
    # on their side; otherwise drop FKs there first).
    op.drop_table("vendors")
