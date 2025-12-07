# table_overrides/states.py

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Callable


def load_states_definitions(csv_path: str | Path) -> List[Dict[str, str]]:
    """
    Load states from a CSV.

    Expected header (preferred): code,name

    If there is no header, assumes two columns in order: code,name.
    """
    path = Path(csv_path)
    rows: List[Dict[str, str]] = []

    if not path.exists():
        return rows

    # Try DictReader first
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames and "code" in reader.fieldnames and "name" in reader.fieldnames:
            for r in reader:
                code = (r.get("code") or "").strip()
                name = (r.get("name") or "").strip()
                if not code:
                    continue
                rows.append({"code": code, "name": name})
            return rows

    # Fallback: plain 2-column CSV
    with path.open("r", encoding="utf-8", newline="") as f2:
        simple_reader = csv.reader(f2)
        for raw in simple_reader:
            if not raw or len(raw) < 2:
                continue
            code = raw[0].strip()
            name = raw[1].strip()
            if not code:
                continue
            rows.append({"code": code, "name": name})

    return rows


def build_states_rows_from_defns(
    table,
    enums: Dict[str, List[str]],
    states_defns: List[Dict[str, str]],
    sample_value: Callable[[Any, Any, Dict[str, List[str]]], Any],
    is_uuid_col: Callable[[Any], bool],
    stable_uuid: Callable[[str], str],
) -> List[Dict[str, Any]]:
    """
    Build rows for the `states` table using CSV definitions.

    We map:
      - CSV code/name into obvious columns
      - id generated via stable_uuid, ignoring any CSV id
      - all other columns via sample_value(...)
    """
    rows: List[Dict[str, Any]] = []

    for st in states_defns:
        code = st["code"]
        name = st["name"]

        row: Dict[str, Any] = {}

        for col in table.columns:
            col_name = col.name

            if col_name in ("code", "state_code", "abbr", "abbreviation"):
                row[col_name] = code
            elif col_name in ("name", "state_name", "full_name"):
                row[col_name] = name
            elif col_name == "id" and is_uuid_col(col):
                # Stable UUID per state code
                row[col_name] = stable_uuid(f"states:{code}")
            else:
                row[col_name] = sample_value(table, col, enums)

        rows.append(row)

    return rows
