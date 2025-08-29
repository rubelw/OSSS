# versions/0022_seed_hr_employees.py
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional

from alembic import op
import sqlalchemy as sa


revision = "0026_seed_facilities_table"
down_revision = "0025_seed_student_table"
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    csv_path = Path(__file__).parent / "facilities.csv"

    with csv_path.open(newline="", encoding="utf-8") as f:
        r = list(csv.DictReader(f))

    if not r:
        print("[facilities] no rows in facilities.csv")
        return

    # Build VALUES
    vals, params = [], {}
    for i, row in enumerate(r):
        vals.append(f"(:sn{i}, :ssid{i}, :slc{i}, :fn{i}, :fc{i}, :aj{i}, :tj{i})")
        params[f"sn{i}"]   = row["school_name"]
        params[f"ssid{i}"] = row["school_state_id"]
        params[f"slc{i}"]  = row["school_local_code"]
        params[f"fn{i}"]   = row["name"]
        params[f"fc{i}"]   = row["code"]
        params[f"aj{i}"]   = row["address_json"]
        params[f"tj{i}"]   = row["attributes_json"]

    values_sql = ", ".join(vals)

    sql = sa.text("""
        WITH src(school_name, school_state_id, school_local_code, name, code, address_json, attributes_json) AS (
            VALUES (:sn0, :ssid0, :slc0, :fn0, :fc0, :aj0, :tj0),
                   (:sn1, :ssid1, :slc1, :fn1, :fc1, :aj1, :tj1),
                   (:sn2, :ssid2, :slc2, :fn2, :fc2, :aj2, :tj2),
                   (:sn3, :ssid3, :slc3, :fn3, :fc3, :aj3, :tj3),
                   (:sn4, :ssid4, :slc4, :fn4, :fc4, :aj4, :tj4),
                   (:sn5, :ssid5, :slc5, :fn5, :fc5, :aj5, :tj5),
                   (:sn6, :ssid6, :slc6, :fn6, :fc6, :aj6, :tj6)
        ),
        matched AS (
            SELECT
                s.id AS school_id,
                src.name,
                src.code,
                COALESCE(src.address_json, '{}')::jsonb    AS address,
                COALESCE(src.attributes_json, '{}')::jsonb AS attributes
            FROM src
            JOIN schools s
              ON  lower(s.name) = lower(src.school_name)
              OR  CAST(s.nces_school_id AS text) = src.school_state_id
              OR  s.school_code = src.school_local_code
              OR  s.building_code = src.school_local_code
        )
        INSERT INTO facilities (school_id, name, code, address, attributes)
        SELECT school_id, name, code, address, attributes
        FROM matched
        WHERE NOT EXISTS (
            SELECT 1 FROM facilities f WHERE f.code = matched.code
        );
    """)
    conn.execute(sql, params)

def downgrade():
    conn = op.get_bind()
    csv_path = Path(__file__).parent / "facilities.csv"
    with csv_path.open(newline="", encoding="utf-8") as f:
        codes = [row["code"] for row in csv.DictReader(f) if row.get("code")]
    if codes:
        for i in range(0, len(codes), 500):
            conn.execute(sa.text("DELETE FROM facilities WHERE code = ANY(:codes)"), {"codes": codes[i:i+500]})