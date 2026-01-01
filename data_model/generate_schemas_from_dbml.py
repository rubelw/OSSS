#!/usr/bin/env python3

"""
/src/OSSS/ai/services/generate_schemas_from_dbml.py

Read schema.dbml and generate a simple schemas.py file for NLP→SQL / data_query:

SCHEMAS: Dict[str, Dict[str, Any]] = {
    "table_name": {
        "columns": {
            "column_name": "normalized_type",
            ...
        },
        "default_select": [...],
        "default_limit": 100,
    },
    ...
}

DO NOT EDIT schemas.py BY HAND.
Re-run this script after changing schema.dbml.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple
import pprint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("generate_schemas_from_dbml")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

THIS_DIR = Path(__file__).resolve().parent
# .../src
PARENT_DIR = THIS_DIR.parents[1]

SRC_DIR = THIS_DIR.parents[2]
# repo root (one level above src)
REPO_ROOT = THIS_DIR.parents[3]

DBML_PATH = THIS_DIR / "schema.dbml"
SCHEMAS_OUTPUT_PATH = (
    PARENT_DIR
    / "OSSS"
    / "src"
    / "OSSS"
    / "ai"
    / "services"
    / "schemas.py"
)

# ---------------------------------------------------------------------------
# System-table detection (reuse same heuristics as wizard generator)
# ---------------------------------------------------------------------------

SYSTEM_TABLE_NAMES = {
    "alembic_version",
    # Add any OSSS-specific system tables here
    # "audit_log",
    # "event_log",
}

SYSTEM_TABLE_PREFIXES = (
    "_",           # e.g. _migration_meta
    "django_",
    "auth_",
    "system_",
)


def is_system_table(table_name: str) -> bool:
    name = table_name.lower()
    if name in SYSTEM_TABLE_NAMES:
        return True
    return any(name.startswith(pfx) for pfx in SYSTEM_TABLE_PREFIXES)


# ---------------------------------------------------------------------------
# DBML parsing
# ---------------------------------------------------------------------------

TABLE_PATTERN = re.compile(
    r'(?mis)^\s*[Tt]able\s+"?(?P<name>[A-Za-z0-9_]+)"?\s*{(?P<body>.*?)}'
)

# Column definition with type, e.g.:
#   id uuid [pk]
#   first_name varchar(255)
COLUMN_DEF_PATTERN = re.compile(
    r'^\s*"?(?P<col>[A-Za-z0-9_]+)"?\s+(?P<type>[A-Za-z0-9_\(\)]+)',
)


def _normalize_dbml_type(dbml_type: str) -> str:
    """
    Map DBML / SQL-ish types to simple canonical type strings for schemas.py.

    Examples:
      - uuid          -> "uuid"
      - varchar(255)  -> "text"
      - text          -> "text"
      - integer       -> "integer"
      - bigint        -> "integer"
      - boolean       -> "bool"
      - timestamptz   -> "timestamp"
      - jsonb         -> "jsonb"
      - numeric(10,2) -> "numeric"
    """
    t = (dbml_type or "").strip().lower()
    # Strip things like "(10,2)" or "[pk]"
    base = re.split(r"[\(\[]", t, maxsplit=1)[0]

    if base == "uuid":
        return "uuid"

    if "char" in base or base in {"text", "string"}:
        return "text"

    if "bool" in base:
        return "bool"

    if base in {"int", "integer", "smallint", "bigint", "serial", "bigserial"} or "int" in base:
        return "integer"

    if "timestamp" in base:
        return "timestamp"

    if base == "date":
        return "date"

    if "json" in base:
        return "jsonb"

    if base in {"numeric", "decimal", "float", "double", "real"}:
        return "numeric"

    # Fallback: just return the cleaned base type
    return base


def parse_dbml_for_schemas(dbml_text: str) -> Dict[str, Dict[str, Any]]:
    """
    Parse DBML into a lightweight table → column/type mapping for schemas.py.

    Returns:
      {
        "table_name": {
          "columns": {
            "col_name": "normalized_type",
            ...
          }
        },
        ...
      }
    """
    tables: Dict[str, Dict[str, Any]] = {}

    for m in TABLE_PATTERN.finditer(dbml_text):
        table_name = m.group("name")
        body = m.group("body")

        columns: Dict[str, str] = {}
        in_note_block = False

        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            # Handle multi-line Note: ''' ... '''
            if in_note_block:
                if "'''" in line:
                    in_note_block = False
                continue

            lower = line.lower()

            if lower.startswith("note"):
                if "'''" in line and line.count("'''") == 1:
                    in_note_block = True
                continue

            # Skip indexes, refs, constraints, nested blocks
            if lower.startswith(("indexes", "index ", "ref:", "primary key", "unique")):
                continue
            if line.endswith("{") or line.startswith("}"):
                continue

            mcol = COLUMN_DEF_PATTERN.match(line)
            if not mcol:
                continue

            col_name = mcol.group("col")
            raw_type = mcol.group("type")
            norm_type = _normalize_dbml_type(raw_type)
            columns[col_name] = norm_type

        if not columns:
            logger.info("Skipping table %s with no columns detected", table_name)
            continue

        tables[table_name] = {"columns": columns}

    return tables


# ---------------------------------------------------------------------------
# SCHEMAS construction helpers
# ---------------------------------------------------------------------------

META_OPTIONAL_FIELDS = {
    "created_at",
    "updated_at",
    "deleted_at",
    "modified_at",
}


def build_default_select(columns: Dict[str, str]) -> List[str]:
    """
    Build a reasonable default_select list for a table.

    Heuristics:
      - Always include 'id' first if present.
      - Prefer non-meta columns over meta columns.
      - Limit to at most 8 columns to keep queries readable.
    """
    names = list(columns.keys())
    default: List[str] = []

    if "id" in names:
        default.append("id")

    for name in names:
        if name == "id":
            continue
        if name in META_OPTIONAL_FIELDS:
            continue
        default.append(name)

    # If everything was filtered out, fall back to all columns
    if not default:
        default = names

    return default[:8]


def build_schemas_mapping(tables: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Convert parsed table/column info into the SCHEMAS mapping:

      {
        "table_name": {
          "columns": {col: type_str, ...},
          "default_select": [...],
          "default_limit": 100,
        },
        ...
      }
    """
    schemas: Dict[str, Dict[str, Any]] = {}

    for table_name, info in sorted(tables.items(), key=lambda kv: kv[0]):
        if is_system_table(table_name):
            logger.info("Skipping system table in SCHEMAS: %s", table_name)
            continue

        columns: Dict[str, str] = dict(info.get("columns") or {})
        if not columns:
            continue

        default_select = build_default_select(columns)
        schemas[table_name] = {
            "columns": columns,
            "default_select": default_select,
            "default_limit": 100,
        }

    return schemas


def render_schemas_py(schemas: Dict[str, Dict[str, Any]]) -> str:
    """
    Render the schemas mapping into a schemas.py source string.
    """
    header = '''"""
Auto-generated schema metadata for NLP→SQL and data_query.

DO NOT EDIT THIS FILE BY HAND.
Regenerate via: python -m OSSS.ai.services.generate_schemas_from_dbml
"""

from typing import Dict, Any


SCHEMAS: Dict[str, Dict[str, Any]] = '''
    # Use pprint for nice formatting and deterministic ordering
    body = pprint.pformat(schemas, indent=4, sort_dicts=True)
    return header + body + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not DBML_PATH.exists():
        raise SystemExit(f"schema.dbml not found at {DBML_PATH}")

    logger.info("Reading DBML from %s", DBML_PATH)
    dbml_text = DBML_PATH.read_text(encoding="utf-8")

    tables = parse_dbml_for_schemas(dbml_text)
    logger.info("Parsed %d tables from DBML", len(tables))

    schemas = build_schemas_mapping(tables)
    logger.info("Built SCHEMAS mapping for %d tables", len(schemas))

    SCHEMAS_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMAS_OUTPUT_PATH.write_text(render_schemas_py(schemas), encoding="utf-8")

    logger.info("schemas.py written to %s", SCHEMAS_OUTPUT_PATH)


if __name__ == "__main__":
    main()
