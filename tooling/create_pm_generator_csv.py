#!/usr/bin/env python3
"""
Create pm_work_generators.csv from the current pm_plans table.

- Works whether pm_plans has columns: code/title/name (any combination).
- Fills plan_code with empty string if there's no 'code' column.
- Picks reasonable defaults for generator fields.

Usage:
  DATABASE_URL=postgresql://osss:password@localhost:5433/osss ./create_pm_generator_csv.py
"""

import csv
import os
import random
from datetime import datetime, timedelta

import sqlalchemy as sa

CSV_OUT = "pm_work_generators.csv"

def main():
    dsn = os.getenv("DATABASE_URL", "postgresql://osss:password@localhost:5433/osss")
    engine = sa.create_engine(dsn, future=True)

    with engine.connect() as conn:
        insp = sa.inspect(conn)
        cols = {c["name"] for c in insp.get_columns("pm_plans")}
        has_code  = "code"  in cols
        has_title = "title" in cols
        has_name  = "name"  in cols

        if not (has_title or has_name):
            raise RuntimeError("pm_plans must have either a 'title' or 'name' column.")

        # Build portable SELECT
        code_expr  = "code" if has_code else "NULL::text"
        title_expr = "title" if has_title else "name"
        order_by   = "1 NULLS LAST, 2" if has_code else "2"  # prefer ordering by code if it exists

        sql = sa.text(f"SELECT {code_expr} AS code, {title_expr} AS title FROM pm_plans ORDER BY {order_by}")
        rows = conn.execute(sql).fetchall()

    # Write CSV expected by your migration
    with open(CSV_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["plan_code","plan_title","frequency_value","frequency_unit","next_run_at","is_active","attributes"])

        for code, title in rows:
            # Defaults (tweak as you like)
            freq_val  = random.choice([7, 14, 30, 60, 90])
            freq_unit = "days"
            next_run  = (datetime.utcnow() + timedelta(days=random.randint(1, 14))).isoformat(timespec="seconds")
            is_active = "true"
            attrs     = ""  # leave blank or put JSON like {"priority":"low"}

            # Ensure strings (code may be None)
            plan_code  = (code or "").strip()
            plan_title = (title or "").strip()

            w.writerow([plan_code, plan_title, freq_val, freq_unit, next_run, is_active, attrs])

    print(f"Wrote {CSV_OUT} with {len(rows)} rows.")

if __name__ == "__main__":
    main()
