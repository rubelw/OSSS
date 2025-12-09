#!/usr/bin/env python3

from __future__ import annotations

import csv
import uuid
import calendar
from decimal import Decimal
from datetime import date
from pathlib import Path

INPUT_CSV = Path("seed_rows.csv")

OUTPUT_ACCOUNTS_CSV = Path("gl_accounts.csv")
OUTPUT_ACCOUNT_SEGMENTS_CSV = Path("gl_account_segments.csv")
OUTPUT_SEGMENTS_CSV = Path("gl_segments.csv")
OUTPUT_SEGMENT_VALUES_CSV = Path("gl_segment_values.csv")
OUTPUT_ACCOUNT_BALANCES_CSV = Path("gl_account_balances.csv")
OUTPUT_FISCAL_PERIODS_CSV = Path("fiscal_periods.csv")
OUTPUT_FISCAL_YEARS_CSV = Path("fiscal_years.csv")

# Mapping of segments (GLSegment)
GL_SEGMENTS = [
    {
        "id": "2b8a4b38-8e3e-41b2-b58e-9c0f1b4e0a01",
        "code": "FUND",
        "name": "Fund",
        "seq": 1,
        "length": 2,
        "required": True,
    },
    {
        "id": "3cf0de8b-5e3a-4f7c-9c65-0c08d8e2b702",
        "code": "FACILITY",
        "name": "Facility",
        "seq": 2,
        "length": 4,
        "required": True,
    },
    {
        "id": "9c8b0f24-4d92-4b7f-9b66-32b9d8f3a903",
        "code": "FUNCTION",
        "name": "Function",
        "seq": 3,
        "length": 4,
        "required": True,
    },
    {
        "id": "7b2c1534-47d4-4b42-9a39-6a2f9a3f5e04",
        "code": "PROGRAM",
        "name": "Program",
        "seq": 4,
        "length": 3,
        "required": True,
    },
    {
        "id": "f10b3d5f-0dd8-4b74-9a6b-bf17a8eddd05",
        "code": "PROJECT",
        "name": "Project",
        "seq": 5,
        "length": 4,
        "required": True,
    },
    {
        "id": "6a2f7b8c-3245-4a1f-8e29-0b3c4d5e6f06",
        "code": "OBJECT",
        "name": "Object",
        "seq": 6,
        "length": 3,
        "required": False,
    },
]


def write_gl_accounts(rows, output):
    """Export GL accounts aligned with GLAccount model."""
    fieldnames = ["id", "code", "name", "acct_type", "active", "attributes"]

    with output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()

        for r in rows:
            w.writerow({
                "id": r["id"],
                "code": r["code"],
                "name": r["name"],
                "acct_type": r.get("acct_type", "expense"),
                "active": r.get("active", True),
                "attributes": r.get("attributes") or "",
            })


def write_gl_segments(output):
    """Export GLSegment dimension table."""
    fieldnames = ["id", "code", "name", "seq", "length", "required"]

    with output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in GL_SEGMENTS:
            w.writerow(r)


def write_gl_account_segments(rows, output):
    """
    Per-account segment breakdown suitable for seeding gl_account_segments.

    We assume gl_account_segments has at least:
      - id (PK)
      - account_id (FK to gl_accounts.id)
      - segment_id (FK to gl_segments.id)
    """
    fieldnames = [
        "id",
        "account_id",
        "segment_id",
        "segment_number",
        "segment_code",
        "segment_name",
    ]

    with output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()

        for r in rows:
            segs = r["code"].split("-")
            segs = (segs + [""] * 6)[:6]  # enforce exactly 6 positions

            for i, (segment_value, segdef) in enumerate(zip(segs, GL_SEGMENTS), start=1):
                if segment_value:
                    seg_name = f"{segdef['name']} {segment_value}"
                else:
                    seg_name = segdef["name"]

                w.writerow({
                    "id": str(uuid.uuid4()),
                    "account_id": r["id"],
                    "segment_id": segdef["id"],
                    "segment_number": i,
                    "segment_code": segment_value,
                    "segment_name": seg_name,
                })


def write_gl_segment_values(rows, output):
    """
    Create GLSegmentValue rows:

    id, code, name, active, segment_id

    Ensures `name` is never empty by falling back to
    "<SegmentName> <code>" or "<SegmentName>".
    """
    fieldnames = ["id", "code", "name", "active", "segment_id"]

    with output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()

        for r in rows:
            seg_values = r["code"].split("-")
            seg_values = (seg_values + [""] * 6)[:6]

            name_parts = r["name"].split(" / ")
            name_parts = (name_parts + [""] * 6)[:6]

            for segval, raw_segname, segdef in zip(seg_values, name_parts, GL_SEGMENTS):
                segname = (raw_segname or "").strip()

                if not segname:
                    if segval:
                        segname = f"{segdef['name']} {segval}"
                    else:
                        segname = segdef["name"]

                w.writerow({
                    "id": str(uuid.uuid4()),
                    "code": segval,
                    "name": segname,
                    "active": True,
                    "segment_id": segdef["id"],
                })


def generate_fiscal_year_rows(
    start_year: int = 2025,
    num_years: int = 1,
) -> list[dict]:
    """
    Generate FiscalYear rows aligned with the FiscalYear model:

    id, year, start_date, end_date, is_closed

    Currently generates simple calendar years (Jan 1 - Dec 31).
    """
    years: list[dict] = []

    for offset in range(num_years):
        yr = start_year + offset
        start = date(yr, 1, 1)
        end = date(yr, 12, 31)

        years.append({
            "id": str(uuid.uuid4()),
            "year": yr,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "is_closed": False,
        })

    return years


def write_fiscal_years(output) -> list[dict]:
    """Write fiscal_years.csv and return the generated year rows."""
    fieldnames = ["id", "year", "start_date", "end_date", "is_closed"]

    years = generate_fiscal_year_rows()

    with output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for y in years:
            w.writerow(y)

    return years


def generate_fiscal_period_rows(
    fiscal_year_row: dict,
    num_periods: int = 12,
) -> list[dict]:
    """
    Generate fiscal period rows aligned with FiscalPeriod model:

    id, year_number, period_no, start_date, end_date, is_closed

    Uses FiscalYear.year as year_number (FK to fiscal_years.year).
    """
    periods: list[dict] = []

    year_number = int(fiscal_year_row["year"])

    for period_no in range(1, num_periods + 1):
        start = date(year_number, period_no, 1)
        last_day = calendar.monthrange(year_number, period_no)[1]
        end = date(year_number, period_no, last_day)

        periods.append({
            "id": str(uuid.uuid4()),
            "year_number": year_number,
            "period_no": period_no,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "is_closed": False,
        })

    return periods


def write_fiscal_periods(output, fiscal_year_row: dict) -> list[dict]:
    """Write fiscal_periods.csv based on a given fiscal year and return periods."""
    fieldnames = [
        "id",
        "year_number",
        "period_no",
        "start_date",
        "end_date",
        "is_closed",
    ]

    periods = generate_fiscal_period_rows(fiscal_year_row=fiscal_year_row)

    with output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for p in periods:
            w.writerow(p)

    return periods


def write_gl_account_balances(rows, fiscal_periods, output):
    """
    Creates dummy account balances:

    id, account_id, fiscal_period_id, begin_balance,
    debit_total, credit_total, end_balance, attributes

    Uses a real fiscal_period_id from the generated fiscal_periods.
    """
    fieldnames = [
        "id",
        "account_id",
        "fiscal_period_id",
        "begin_balance",
        "debit_total",
        "credit_total",
        "end_balance",
        "attributes",
    ]

    # Use the last period (e.g., period 12 / December) as the balance period
    if fiscal_periods:
        target_period_id = fiscal_periods[-1]["id"]
    else:
        # Fallback (should not happen in normal flow)
        target_period_id = str(uuid.uuid4())

    with output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()

        for r in rows:
            debit = Decimal("100.00")
            credit = Decimal("50.00")
            begin = Decimal("0.00")
            end = begin + debit - credit

            w.writerow({
                "id": str(uuid.uuid4()),
                "account_id": r["id"],
                "fiscal_period_id": target_period_id,
                # write as strings; Alembic/migration can cast to NUMERIC/DECIMAL
                "begin_balance": f"{begin:.2f}",
                "debit_total": f"{debit:.2f}",
                "credit_total": f"{credit:.2f}",
                "end_balance": f"{end:.2f}",
                # valid JSON for attributes
                "attributes": "{}",  # JSON object, not empty string
            })


def main():
    with INPUT_CSV.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    write_gl_accounts(rows, OUTPUT_ACCOUNTS_CSV)
    write_gl_segments(OUTPUT_SEGMENTS_CSV)
    write_gl_account_segments(rows, OUTPUT_ACCOUNT_SEGMENTS_CSV)
    write_gl_segment_values(rows, OUTPUT_SEGMENT_VALUES_CSV)

    # New: generate fiscal years and periods, then use periods for balances
    fiscal_years = write_fiscal_years(OUTPUT_FISCAL_YEARS_CSV)
    if fiscal_years:
        fiscal_year_row = fiscal_years[0]
    else:
        # Defensive fallback, but under normal circumstances this won't happen
        fiscal_year_row = {
            "id": str(uuid.uuid4()),
            "year": 2025,
            "start_date": date(2025, 1, 1).isoformat(),
            "end_date": date(2025, 12, 31).isoformat(),
            "is_closed": False,
        }

    fiscal_periods = write_fiscal_periods(OUTPUT_FISCAL_PERIODS_CSV, fiscal_year_row)
    write_gl_account_balances(rows, fiscal_periods, OUTPUT_ACCOUNT_BALANCES_CSV)

    print("Wrote:")
    print(" -", OUTPUT_ACCOUNTS_CSV)
    print(" -", OUTPUT_ACCOUNT_SEGMENTS_CSV)
    print(" -", OUTPUT_SEGMENTS_CSV)
    print(" -", OUTPUT_SEGMENT_VALUES_CSV)
    print(" -", OUTPUT_FISCAL_YEARS_CSV)
    print(" -", OUTPUT_FISCAL_PERIODS_CSV)
    print(" -", OUTPUT_ACCOUNT_BALANCES_CSV)


if __name__ == "__main__":
    main()
