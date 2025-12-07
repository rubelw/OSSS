# table_overrides/organizations.py

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Callable


def build_organizations_rows_from_csv(
    table,
    enums: Dict[str, List[str]],
    csv_path: str | Path,
    sample_value: Callable[[Any, Any, Dict[str, List[str]]], Any],
    is_uuid_col: Callable[[Any], bool],
    stable_uuid: Callable[[str], str],
) -> List[Dict[str, Any]]:
    """
    Build rows for the `organizations` table from a CSV.

    Expected header (at least):
      id,updated_at,created_at,name,code

    We IGNORE the CSV 'id' and always generate our own stable UUID.
    Other columns come from CSV when present, otherwise sample_value().
    """
    path = Path(csv_path)
    if not path.exists():
        return []

    rows: List[Dict[str, Any]] = []

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return []

        for idx, raw in enumerate(reader):
            row: Dict[str, Any] = {}

            for col in table.columns:
                col_name = col.name
                raw_val = raw.get(col_name)

                # Always generate our own UUID for id
                if col_name == "id" and is_uuid_col(col):
                    seed_payload = {k: v for k, v in raw.items() if k != "id"}
                    seed = f"{table.name}:{idx}:{sorted(seed_payload.items())}"
                    row[col_name] = stable_uuid(seed)
                    continue

                if raw_val not in (None, ""):
                    # For orgs this is mostly strings/timestamps; let DB coerce timestamps
                    row[col_name] = raw_val
                else:
                    row[col_name] = sample_value(table, col, enums)

            rows.append(row)

    return rows
