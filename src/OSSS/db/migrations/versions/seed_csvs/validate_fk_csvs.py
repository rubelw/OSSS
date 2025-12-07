#!/usr/bin/env python3
"""
Validate FK consistency across generated CSV files.

Directory layout:

    project_root/
        schema.dbml
        csv/
            *.csv
        seed_csvs/
            validate_fk_csvs.py
            manual_fk_map.py   (optional but recommended)

Defaults assume this layout:
  --dbml    ../schema.dbml
  --csv-dir ../csv
"""

from __future__ import annotations
import argparse
import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

# ------------------------------------------------------------
# Regex
# ------------------------------------------------------------

UUID_CHAR_PATTERN = re.compile(r"char\s*\(\s*36\s*\)", re.I)
STRING_LEN_RE = re.compile(r"\(\s*(\d+)\s*\)")

TABLE_START_RE = re.compile(r"^\s*Table\s+`?([\w]+)`?\s*{")
COLUMN_RE = re.compile(r"^\s*`?(\w+)`?\s+([^\s\[]+)(.*)$")
REF_RE = re.compile(
    r"Ref\s*:\s*`?(\w+)`?\.(\w+)\s*>\s*`?(\w+)`?\.(\w+)",
    re.IGNORECASE,
)

# ------------------------------------------------------------
# Data Structures
# ------------------------------------------------------------

@dataclass
class Column:
    name: str
    type: str
    is_pk: bool = False

@dataclass
class ForeignKey:
    child_table: str
    child_column: str
    parent_table: str
    parent_column: str

@dataclass
class Table:
    name: str
    columns: List[Column] = field(default_factory=list)
    fks_out: List[ForeignKey] = field(default_factory=list)
    fks_in: List[ForeignKey] = field(default_factory=list)

# ------------------------------------------------------------
# DBML Parsing
# ------------------------------------------------------------

def parse_dbml(dbml_path: Path):
    text = dbml_path.read_text()
    lines = text.splitlines()

    tables: Dict[str, Table] = {}
    fks: List[ForeignKey] = []
    current: Optional[Table] = None

    for raw in lines:
        line = raw.strip()

        # DBML Ref lines
        if line.startswith("Ref"):
            m = REF_RE.search(line)
            if m:
                ctable, ccol, ptable, pcol = m.groups()
                fks.append(ForeignKey(ctable, ccol, ptable, pcol))
            continue

        # Table start
        m_table = TABLE_START_RE.match(raw)
        if m_table:
            name = m_table.group(1)
            current = Table(name)
            tables[name] = current
            continue

        # Table end
        if current and line.startswith("}"):
            current = None
            continue

        # Columns (ignore Indexes / Note blocks)
        if current and raw and not raw.strip().startswith(("Indexes", "Note")):
            no_comment = raw.split("//")[0].strip()
            m = COLUMN_RE.match(no_comment)
            if m:
                col_name, col_type, rest = m.groups()
                current.columns.append(
                    Column(col_name, col_type.lower(), "pk" in rest)
                )

    # link FK objects
    for fk in fks:
        if fk.child_table in tables and fk.parent_table in tables:
            tables[fk.child_table].fks_out.append(fk)
            tables[fk.parent_table].fks_in.append(fk)

    return tables, fks

# ------------------------------------------------------------
# Manual FK overlay (from manual_fk_map.py)
# ------------------------------------------------------------

def add_manual_fks_from_map(tables: Dict[str, Table], fks: List[ForeignKey]) -> None:
    """
    Overlay FKs from manual_fk_map.MANUAL_FK_MAP on top of DBML FKs.
    This keeps validation in sync with the CSV generator.
    """
    try:
        from manual_fk_map import MANUAL_FK_MAP  # type: ignore
    except ImportError:
        print("[INFO] No manual_fk_map.py found; skipping manual FK overlay.")
        return

    if not MANUAL_FK_MAP:
        print("[INFO] MANUAL_FK_MAP is empty; skipping manual FK overlay.")
        return

    existing_pairs: Set[Tuple[str, str, str, str]] = {
        (fk.child_table, fk.child_column, fk.parent_table, fk.parent_column)
        for fk in fks
    }

    added = 0
    overridden = 0

    print("\n=== Manual FK overlay from MANUAL_FK_MAP ===")

    for child_table, col_map in MANUAL_FK_MAP.items():
        if child_table not in tables:
            print(f"  [WARN] MANUAL_FK_MAP references missing child table '{child_table}'")
            continue

        for child_col, (parent_table, parent_col) in col_map.items():
            if parent_table not in tables:
                print(
                    f"  [WARN] MANUAL_FK_MAP {child_table}.{child_col} → "
                    f"{parent_table}.{parent_col}: parent table missing in DBML"
                )
                continue

            key = (child_table, child_col, parent_table, parent_col)

            # Remove any existing FK on the same child_table.child_column,
            # so manual map becomes the source of truth.
            existing_for_col = [
                fk for fk in tables[child_table].fks_out
                if fk.child_column == child_col
            ]
            for old_fk in existing_for_col:
                tables[child_table].fks_out.remove(old_fk)
                tables[old_fk.parent_table].fks_in = [
                    fk for fk in tables[old_fk.parent_table].fks_in
                    if not (fk.child_table == child_table and fk.child_column == child_col)
                ]
                overridden += 1

            if key in existing_pairs:
                # Already have exactly this mapping
                continue

            fk = ForeignKey(
                child_table=child_table,
                child_column=child_col,
                parent_table=parent_table,
                parent_column=parent_col,
            )
            tables[child_table].fks_out.append(fk)
            tables[parent_table].fks_in.append(fk)
            fks.append(fk)
            existing_pairs.add(key)
            added += 1

            print(f"  manual {child_table}.{child_col} -> {parent_table}.{parent_col}")

    print(f"=== End manual FK overlay (added {added}, overridden {overridden}) ===\n")

# ------------------------------------------------------------
# Heuristic FK inference
# ------------------------------------------------------------

def infer_parent_table(col_name: str, tables: Dict[str, Table]) -> Optional[str]:
    if not col_name.endswith("_id"):
        return None

    base = col_name[:-3]
    candidates = [base, base + "s", base + "es"]

    if base.endswith("y"):
        candidates.append(base[:-1] + "ies")

    for cand in candidates:
        if cand in tables and any(c.name == "id" for c in tables[cand].columns):
            return cand
    return None

def add_heuristic_fks(tables: Dict[str, Table], fks: List[ForeignKey]) -> None:
    existing = {(fk.child_table, fk.child_column) for fk in fks}

    print("\n=== Heuristic FK inference ===")

    added = 0
    for table in tables.values():
        for col in table.columns:
            key = (table.name, col.name)

            if key in existing:
                continue
            if not col.name.endswith("_id"):
                continue

            parent = infer_parent_table(col.name, tables)
            if not parent:
                continue

            fk = ForeignKey(table.name, col.name, parent, "id")
            table.fks_out.append(fk)
            tables[parent].fks_in.append(fk)
            fks.append(fk)
            existing.add(key)
            added += 1

            print(f"  inferred {table.name}.{col.name} -> {parent}.id")

    print(f"=== End heuristic inference (added {added}) ===\n")

# ------------------------------------------------------------
# CSV validation helpers
# ------------------------------------------------------------

def load_parent_values(csv_dir: Path, tables: Dict[str, Table]) -> Dict[Tuple[str, str], Set[str]]:
    parent_values: Dict[Tuple[str, str], Set[str]] = {}

    needed: Set[Tuple[str, str]] = set()
    for table in tables.values():
        for fk in table.fks_out:
            needed.add((fk.parent_table, fk.parent_column))

    for (table_name, col) in sorted(needed):
        csv_path = csv_dir / f"{table_name}.csv"

        if not csv_path.exists():
            print(f"[WARN] Missing parent CSV: {csv_path}")
            continue

        vals: Set[str] = set()
        with csv_path.open(newline="", encoding="utf8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or col not in reader.fieldnames:
                print(f"[WARN] Missing column {col} in {csv_path}")
                continue

            for row in reader:
                raw = row.get(col, "")
                v = raw.strip()
                if v:
                    vals.add(v)

        parent_values[(table_name, col)] = vals
        print(f"[INFO] Loaded {len(vals)} values for {table_name}.{col}")

    return parent_values


def validate_fks(
    csv_dir: Path,
    tables: Dict[str, Table],
    parent_values: Dict[Tuple[str, str], Set[str]],
    report_lines: List[str],
) -> int:
    violations = 0

    print("\n=== FK Validation ===")
    report_lines.append("=== FK Validation Report ===")

    for table in sorted(tables.values(), key=lambda t: t.name):
        if not table.fks_out:
            continue

        csv_path = csv_dir / f"{table.name}.csv"
        if not csv_path.exists():
            msg = f"[WARN] Missing child CSV: {csv_path}"
            print(msg)
            report_lines.append(msg)
            continue

        with csv_path.open(newline="", encoding="utf8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = reader.fieldnames or []

        print(f"\nChecking {table.name} ({len(rows)} rows)")
        report_lines.append(f"\nTable {table.name}: {len(rows)} rows")

        for fk in table.fks_out:
            parent_key = (fk.parent_table, fk.parent_column)
            parent_set = parent_values.get(parent_key)

            if fk.child_column not in fieldnames:
                msg = (f"  SKIP {fk.child_column} -> {fk.parent_table}.{fk.parent_column} "
                       f"(missing child column in {table.name}.csv)")
                print(msg)
                report_lines.append(msg)
                continue

            if parent_set is None:
                msg = (f"  SKIP {fk.child_column} -> {fk.parent_table}.{fk.parent_column} "
                       f"(no parent values loaded)")
                print(msg)
                report_lines.append(msg)
                continue

            bad: List[Tuple[int, str]] = []
            for idx, row in enumerate(rows, start=1):
                raw = row.get(fk.child_column, "")
                val = raw.strip()
                if val == "":
                    # treat blank as NULL → ignore
                    continue
                if val not in parent_set:
                    bad.append((idx, val))

            if not bad:
                msg = f"  OK   {fk.child_column} -> {fk.parent_table}.{fk.parent_column}"
                print(msg)
                report_lines.append(msg)
            else:
                msg = (f"  FAIL {fk.child_column} -> {fk.parent_table}.{fk.parent_column} "
                       f"({len(bad)} violations)")
                print(msg)
                report_lines.append(msg)
                for idx, v in bad[:5]:
                    detail = f"      row {idx}: {v}"
                    print(detail)
                    report_lines.append(detail)
                violations += len(bad)

    print("\n=== Validation Complete ===")
    if violations == 0:
        print("All foreign keys valid 🎉")
        report_lines.append("\nAll foreign keys valid 🎉")
    else:
        print(f"{violations} FK violations found")
        report_lines.append(f"\n{violations} FK violations found")
    return violations

# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dbml", default="./schema.dbml")
    parser.add_argument("--csv-dir", default="../csv")
    parser.add_argument(
        "--output",
        default="fk_validation_output.txt",
        help="Path (relative to csv-dir) for the validation report file.",
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    dbml = (script_dir / args.dbml).resolve()
    csv_dir = (script_dir / args.csv_dir).resolve()
    output_path = csv_dir / args.output

    print(f"[INFO] DBML: {dbml}")
    print(f"[INFO] CSV Directory: {csv_dir}")

    tables, fks = parse_dbml(dbml)
    add_manual_fks_from_map(tables, fks)
    add_heuristic_fks(tables, fks)

    report_lines: List[str] = []
    parent_values = load_parent_values(csv_dir, tables)
    violations = validate_fks(csv_dir, tables, parent_values, report_lines)

    # Write report
    try:
        output_path.write_text("\n".join(report_lines), encoding="utf8")
        print(f"\n[INFO] Detailed report written to: {output_path}")
    except Exception as e:
        print(f"[WARN] Failed to write report to {output_path}: {e}")

    if args.strict and violations > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
