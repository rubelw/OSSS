#!/usr/bin/env python3

# compare_dbml_to_csv.py
#
# Place this file in: /data_model/
# It compares:
#   - DBML tables from: /data_model/schema.dbml
#   - CSV files from:   /src/OSSS/db/migrations/data_csv
#
# Run:
#   python data_model/compare_dbml_to_csv.py
#

from pathlib import Path

# Paths relative to project root
DATA_MODEL_DIR = Path(__file__).parent
DBML_PATH = DATA_MODEL_DIR / "schema.dbml"
CSV_DIR = Path(__file__).parent.parent / "src" / "OSSS" / "db" / "migrations" / "data_csv"

# --- validate paths ---
if not DBML_PATH.is_file():
    raise SystemExit(f"❌ DBML not found: {DBML_PATH.resolve()}")

if not CSV_DIR.is_dir():
    raise SystemExit(f"❌ CSV directory not found: {CSV_DIR.resolve()}")

# --- 1) Parse DBML for table names ---
dbml_tables: list[str] = []
current = None

for raw in DBML_PATH.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if line.startswith("Table "):
        # Handles: Table users {  OR Table "users" {
        name = line.split()[1].strip('"`[]{}')
        current = name
        dbml_tables.append(name)
        continue
    if current and line.startswith("}"):
        current = None

dbml_set = set(dbml_tables)

# --- 2) Extract CSV base names ---
csv_tables = [p.stem for p in sorted(CSV_DIR.glob("*.csv"))]
csv_set = set(csv_tables)

# --- 3) Compare sets ---
csv_in_dbml = sorted(csv_set & dbml_set)
csv_missing_from_dbml = sorted(csv_set - dbml_set)
dbml_missing_csv = sorted(dbml_set - csv_set)

# --- 4) Output results ---
print("\n==================== SUMMARY ====================")
print(f"DBML tables found:        {len(dbml_set)}")
print(f"CSV files found:          {len(csv_set)}")
print(f"CSV tables in DBML:       {len(csv_in_dbml)}")
print(f"CSV tables NOT in DBML:   {len(csv_missing_from_dbml)}")
print(f"DBML tables missing CSV:  {len(dbml_missing_csv)}")

print("\n========== CSV TABLES FOUND IN DBML ==========")
for t in csv_in_dbml:
    print(f"  ✓ {t}")

print("\n====== CSV FILES *NOT* PRESENT IN DBML ======")
for t in csv_missing_from_dbml:
    print(f"  ✗ {t}")

print("\n====== DBML TABLES WITH NO CSV FILE ======")
for t in dbml_missing_csv:
    print(f"  • {t}")

print("\nDone.\n")
