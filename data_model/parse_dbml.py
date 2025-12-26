#!/usr/bin/env python3

from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import json
from pathlib import Path

from pydbml import PyDBML  # ✅ use PyDBML, not DBML

BASE_DIR = Path(__file__).resolve().parent
DBML_PATH = BASE_DIR / "schema.dbml"
OUT_PATH = BASE_DIR / "schema.json"


@dataclass
class ColumnSchema:
    name: str
    type: str
    not_null: bool
    pk: bool
    unique: bool
    default: Optional[str]
    note: Optional[str]


@dataclass
class TableSchema:
    name: str
    note: Optional[str]
    columns: List[ColumnSchema]
    indexes: List[str]
    relations: List[str]


def load_dbml(path: Path):
    """
    Load the DBML using PyDBML.

    PyDBML accepts:
      - Path
      - file-like object
      - or source string
    """
    print(f"[parse_dbml] Loading DBML → {path}")
    # You can pass the Path directly:
    return PyDBML(path)


def extract_schema(dbml: PyDBML) -> Dict[str, TableSchema]:
    tables: Dict[str, TableSchema] = {}

    for t in dbml.tables:
        columns: List[ColumnSchema] = []
        for c in t.columns:
            columns.append(
                ColumnSchema(
                    name=c.name,
                    type=str(c.type),              # ensure it's a string
                    not_null=c.not_null,           # ✅ correct attribute name
                    pk=c.pk,                       # primary key flag
                    unique=c.unique,               # unique constraint
                    default=str(c.default) if c.default is not None else None,
                    note=(c.note.text if c.note else None),
                )
            )

        indexes = [idx.name or str(idx) for idx in t.indexes]

        tables[t.name] = TableSchema(
            name=t.name,
            note=t.note.text if t.note else None,
            columns=columns,
            indexes=indexes,
            relations=[],  # we can wire actual relations later if you want
        )

    return tables


def main():
    if not DBML_PATH.exists():
        raise SystemExit(f"[parse_dbml] ERROR: {DBML_PATH} does not exist")

    dbml = load_dbml(DBML_PATH)
    schema = extract_schema(dbml)

    out = {tbl.name: asdict(tbl) for tbl in schema.values()}
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print(f"[parse_dbml] ✔ wrote → {OUT_PATH}")


if __name__ == "__main__":
    main()
