# versions/0022_seed_hr_employees.py
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional
import logging

from alembic import op
import sqlalchemy as sa


revision = "0025_seed_student_table"
down_revision = "0024_seed_students"
branch_labels = None
depends_on = None

# --- logging ---------------------------------------------------------------
# Alembic’s env.py typically configures logging via fileConfig, so use an
# Alembic-namespaced logger to have messages show with the rest of the output.
log = logging.getLogger("alembic.runtime.migration")
LOG_SAMPLE = 6  # how many example rows to show in logs


# --- helpers ---------------------------------------------------------------
def _norm(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = s.strip()
    return s or None


def _read_csv(csv_path: Path) -> List[Dict[str, Optional[str]]]:
    if not csv_path.exists():
        log.error("[students] CSV not found: %s", csv_path)
        return []
    with csv_path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        rows: List[Dict[str, Optional[str]]] = []
        for row in r:
            rows.append(
                {
                    "first_name": _norm(row.get("first_name")),
                    "middle_name": _norm(row.get("middle_name")),
                    "last_name": _norm(row.get("last_name")),
                    # email intentionally ignored / dropped
                    "student_number": _norm(row.get("student_number")),
                    "graduation_year": _norm(row.get("graduation_year")),
                }
            )
        return rows


def _log_sample(title: str, rows: List[Dict[str, object]], keys: List[str], limit: int = LOG_SAMPLE):
    if not rows:
        log.debug("%s: (none)", title)
        return
    subset = rows[:limit]
    pretty = [{k: r.get(k) for k in keys} for r in subset]
    log.debug("%s (showing %d of %d): %s", title, len(pretty), len(rows), pretty)


# --- migration -------------------------------------------------------------
def upgrade():
    conn = op.get_bind()

    try:
        # --- load CSV
        csv_path = (Path(__file__).parent / "students.csv").resolve()
        log.debug("[students] Reading CSV at: %s", csv_path)
        raw_rows = _read_csv(csv_path)
        log.debug("[students] Total rows read: %d", len(raw_rows))
        _log_sample(
            "[students] Sample raw rows",
            raw_rows,
            ["first_name", "middle_name", "last_name", "student_number", "graduation_year"],
        )

        # filter usable rows
        rows = [
            r
            for r in raw_rows
            if r["first_name"] and r["last_name"] and r["student_number"] and r["graduation_year"]
        ]
        log.debug("[students] Usable rows after filter: %d", len(rows))
        if not rows:
            log.warning("[students] No usable rows → done")
            return

        # --- prepare VALUES block once (no email)
        vals, params = [], {}
        for i, r in enumerate(rows):
            vals.append(f"(:fn{i}, :mn{i}, :ln{i}, :sn{i}, :gy{i})")
            params[f"fn{i}"] = r["first_name"]
            params[f"mn{i}"] = r["middle_name"]
            params[f"ln{i}"] = r["last_name"]
            params[f"sn{i}"] = r["student_number"]
            try:
                params[f"gy{i}"] = int(r["graduation_year"])
            except (TypeError, ValueError):
                log.warning("[students] Bad graduation_year for %s → %r", r.get("student_number"), r.get("graduation_year"))
                params[f"gy{i}"] = None

        values_sql = ", ".join(vals)

        # --- Insert students for UNIQUE name matches only
        insert_sql = sa.text(
            f"""
            WITH s(first_name,middle_name,last_name,student_number,graduation_year) AS (
                VALUES {values_sql}
            ),
            cand AS (
                SELECT
                    s.student_number,
                    s.graduation_year,
                    p.id AS person_id
                FROM s
                JOIN persons p
                  ON trim(lower(p.first_name)) = trim(lower(s.first_name))
                 AND COALESCE(trim(lower(p.middle_name)),'') = COALESCE(trim(lower(s.middle_name)),'')
                 AND trim(lower(p.last_name))  = trim(lower(s.last_name))
            ),
            uniq AS (
                SELECT *
                FROM (
                    SELECT c.*,
                           COUNT(*) OVER (PARTITION BY c.student_number) AS cnt
                    FROM cand c
                ) z
                WHERE cnt = 1
            )
            INSERT INTO students (person_id, student_number, graduation_year)
            SELECT
                u.person_id,
                u.student_number,
                u.graduation_year
            FROM uniq u
            WHERE u.person_id IS NOT NULL
              AND u.student_number IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM students st WHERE st.student_number = u.student_number)
              AND NOT EXISTS (SELECT 1 FROM students st WHERE st.person_id = u.person_id)
            """
        )
        r_ins = conn.execute(insert_sql, params)
        ins_count = r_ins.rowcount if getattr(r_ins, "rowcount", None) not in (None, -1) else 0
        log.debug("[students] Inserted (unique name matches): %s", ins_count)

        # --- Diagnostics: ambiguous matches (same CSV row matches >1 person)
        ambiguous = conn.execute(
            sa.text(
                f"""
                WITH s(first_name,middle_name,last_name,student_number,graduation_year) AS (
                    VALUES {values_sql}
                ),
                cand AS (
                    SELECT
                        s.student_number,
                        s.graduation_year,
                        p.id AS person_id
                    FROM s
                    JOIN persons p
                      ON trim(lower(p.first_name)) = trim(lower(s.first_name))
                     AND COALESCE(trim(lower(p.middle_name)),'') = COALESCE(trim(lower(s.middle_name)),'')
                     AND trim(lower(p.last_name))  = trim(lower(s.last_name))
                ),
                counts AS (
                    SELECT student_number, COUNT(*) AS cnt
                    FROM cand
                    GROUP BY student_number
                    HAVING COUNT(*) > 1
                )
                SELECT c.student_number, c.graduation_year, c.person_id
                FROM cand c
                JOIN counts x USING (student_number)
                ORDER BY c.student_number
                LIMIT :lim
                """
            ),
            {**params, "lim": LOG_SAMPLE},
        ).mappings().all()
        # Group sample by student_number for nicer log
        amb_sample = []
        seen = set()
        for r in ambiguous:
            sn = r["student_number"]
            if sn in seen:
                continue
            same = [x for x in ambiguous if x["student_number"] == sn]
            amb_sample.append({"student_number": sn, "person_ids": [x["person_id"] for x in same]})
            seen.add(sn)
            if len(amb_sample) >= LOG_SAMPLE:
                break

        amb_count = conn.execute(
            sa.text(
                f"""
                WITH s(first_name,middle_name,last_name,student_number,graduation_year) AS (
                    VALUES {values_sql}
                ),
                cand AS (
                    SELECT s.student_number, p.id AS person_id
                    FROM s
                    JOIN persons p
                      ON trim(lower(p.first_name)) = trim(lower(s.first_name))
                     AND COALESCE(trim(lower(p.middle_name)),'') = COALESCE(trim(lower(s.middle_name)),'')
                     AND trim(lower(p.last_name))  = trim(lower(s.last_name))
                )
                SELECT COUNT(*) FROM (
                    SELECT student_number
                    FROM cand
                    GROUP BY student_number
                    HAVING COUNT(*) > 1
                ) t
                """
            ),
            params,
        ).scalar_one()
        log.debug("[students] Ambiguous CSV rows (matched >1 person): %s", amb_count)
        if amb_sample:
            log.debug("[students] Sample ambiguous rows: %s", amb_sample)

        # --- Diagnostics: no-match rows (matched 0 persons)
        no_match = conn.execute(
            sa.text(
                f"""
                WITH s(first_name,middle_name,last_name,student_number,graduation_year) AS (
                    VALUES {values_sql}
                ),
                cand AS (
                    SELECT s.student_number
                    FROM s
                    JOIN persons p
                      ON trim(lower(p.first_name)) = trim(lower(s.first_name))
                     AND COALESCE(trim(lower(p.middle_name)),'') = COALESCE(trim(lower(s.middle_name)),'')
                     AND trim(lower(p.last_name))  = trim(lower(s.last_name))
                    GROUP BY s.student_number
                )
                SELECT s.first_name, s.middle_name, s.last_name, s.student_number, s.graduation_year
                FROM s
                LEFT JOIN cand USING (student_number)
                WHERE cand.student_number IS NULL
                ORDER BY s.student_number
                LIMIT :lim
                """
            ),
            {**params, "lim": LOG_SAMPLE},
        ).mappings().all()
        no_match_count = conn.execute(
            sa.text(
                f"""
                WITH s(first_name,middle_name,last_name,student_number,graduation_year) AS (
                    VALUES {values_sql}
                ),
                cand AS (
                    SELECT s.student_number
                    FROM s
                    JOIN persons p
                      ON trim(lower(p.first_name)) = trim(lower(s.first_name))
                     AND COALESCE(trim(lower(p.middle_name)),'') = COALESCE(trim(lower(s.middle_name)),'')
                     AND trim(lower(p.last_name))  = trim(lower(s.last_name))
                    GROUP BY s.student_number
                )
                SELECT COUNT(*)
                FROM s
                LEFT JOIN cand USING (student_number)
                WHERE cand.student_number IS NULL
                """
            ),
            params,
        ).scalar_one()
        log.debug("[students] No-match CSV rows (matched 0 persons): %s", no_match_count)
        _log_sample("[students] Sample no-match rows", no_match,
                    ["first_name", "middle_name", "last_name", "student_number", "graduation_year"])

        # --- Final report
        log.debug("[students] Migration complete. Inserted=%s, Ambiguous=%s, NoMatch=%s",
                 ins_count, amb_count, no_match_count)

    except Exception:
        log.exception("[students] Upgrade failed with an exception")
        raise


def downgrade():
    conn = op.get_bind()
    try:
        csv_path = (Path(__file__).parent / "students.csv").resolve()
        sns = [r["student_number"] for r in _read_csv(csv_path) if r.get("student_number")]
        if not sns:
            log.debug("[students] downgrade: no student_numbers found in CSV")
            return
        total = 0
        for i in range(0, len(sns), 500):
            chunk = sns[i : i + 500]
            res = conn.execute(sa.text("DELETE FROM students WHERE student_number = ANY(:sns)"), {"sns": chunk})
            rc = res.rowcount if getattr(res, "rowcount", None) not in (None, -1) else len(chunk)
            total += rc
        log.debug("[students] downgrade: deleted rows: %s", total)
    except Exception:
        log.exception("[students] Downgrade failed with an exception")
        raise