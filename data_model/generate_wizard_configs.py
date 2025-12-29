#!/usr/bin/env python3

# /data_models/generate_wizard_configs.py
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("generate_wizard_configs")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

THIS_DIR = Path(__file__).resolve().parent
DBML_PATH = THIS_DIR / "schema.dbml"
WIZARD_CONFIGS_PATH = (
    THIS_DIR.parent
    / "src"
    / "OSSS"
    / "ai"
    / "agents"
    / "data_query"
    / "wizard_configs.json"
)

# ---------------------------------------------------------------------------
# System-table detection
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

# Inline ref on a column line, e.g.:
#   user_id uuid [ref: > users.id]
INLINE_REF_PATTERN = re.compile(
    r'\bref:\s*[<>\-]\s*(?P<table>[A-Za-z0-9_]+)\.(?P<col>[A-Za-z0-9_]+)',
    re.IGNORECASE,
)

# Top-level refs, e.g.:
#   Ref: orders.user_id > users.id
#   Ref: users.id < orders.user_id
REF_PATTERN = re.compile(
    r'(?mi)^\s*Ref:\s*(?P<left>[A-Za-z0-9_]+\.[A-Za-z0-9_]+)\s*'
    r'(?P<arrow>[<>\-])\s*'
    r'(?P<right>[A-Za-z0-9_]+\.[A-Za-z0-9_]+)'
)


def parse_dbml_tables(dbml_text: str) -> Dict[str, Dict[str, Any]]:
    """
    Return:
      {
        table_name: {
          "columns": [column_name, ...],
          "foreign_keys": {
              column_name: {
                  "ref_table": str,
                  "ref_column": str,
              },
              ...
          },
        },
        ...
      }

    We keep this intentionally lightweight and conservative:
    - Only treat lines that look like "column_name type ..." as columns.
    - Skip Notes, Indexes, Refs, etc.
    - Foreign keys are detected from:
        * inline [ref: ...] in column lines
        * top-level Ref: ... lines
    """
    tables: Dict[str, Dict[str, Any]] = {}

    # First pass: parse tables, columns, and inline refs
    for m in TABLE_PATTERN.finditer(dbml_text):
        table_name = m.group("name")
        body = m.group("body")

        cols: List[str] = []
        foreign_keys: Dict[str, Dict[str, str]] = {}
        in_note_block = False

        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            # ----- Note blocks: Note: ''' ... ''' -----
            if in_note_block:
                if "'''" in line:
                    in_note_block = False
                continue

            lower = line.lower()

            if lower.startswith("note"):
                # If triple-quote appears and doesn't close on same line, enter note block
                if "'''" in line and line.count("'''") == 1:
                    in_note_block = True
                continue

            # Skip index / reference / constraint lines
            if lower.startswith(("indexes", "index ", "ref:", "primary key", "unique")):
                continue

            # Skip nested blocks
            if line.endswith("{") or line.startswith("}"):
                continue

            # Column definition: first token is the column name, second token is type
            mcol = re.match(
                r'^"?(?P<col>[A-Za-z0-9_]+)"?\s+[A-Za-z0-9_\[\]\(\),]+',
                line,
            )
            if not mcol:
                continue

            col_name = mcol.group("col")
            cols.append(col_name)

            # Look for inline ref on the same line, e.g. [ref: > users.id]
            inline_ref = INLINE_REF_PATTERN.search(line)
            if inline_ref:
                ref_table = inline_ref.group("table")
                ref_col = inline_ref.group("col")
                foreign_keys.setdefault(col_name, {
                    "ref_table": ref_table,
                    "ref_column": ref_col,
                })

        tables[table_name] = {
            "columns": cols,
            "foreign_keys": foreign_keys,
        }

    # Second pass: parse top-level Ref: lines and enrich foreign_keys
    for m in REF_PATTERN.finditer(dbml_text):
        left = m.group("left")   # e.g. orders.user_id
        arrow = m.group("arrow") # <, >, or -
        right = m.group("right") # e.g. users.id

        left_table, left_col = left.split(".")
        right_table, right_col = right.split(".")

        # Decide which side is the foreign key (referencing) vs referenced.
        # DBML convention:
        #   Ref: users.id < orders.user_id   -> orders.user_id references users.id
        #   Ref: orders.user_id > users.id   -> orders.user_id references users.id
        if arrow == ">":
            fk_table, fk_col = left_table, left_col
            ref_table, ref_col = right_table, right_col
        elif arrow == "<":
            fk_table, fk_col = right_table, right_col
            ref_table, ref_col = left_table, left_col
        else:
            # '-' (many-to-many or unspecified direction).
            # Treat left as FK referencing right to at least capture a usable mapping.
            fk_table, fk_col = left_table, left_col
            ref_table, ref_col = right_table, right_col

        tinfo = tables.get(fk_table)
        if not tinfo:
            continue

        fk_map = tinfo.setdefault("foreign_keys", {})
        # Don't override inline ref info if already present
        fk_map.setdefault(fk_col, {
            "ref_table": ref_table,
            "ref_column": ref_col,
        })

    return tables


# ---------------------------------------------------------------------------
# Wizard config generation / merge
# ---------------------------------------------------------------------------

META_OPTIONAL_FIELDS = {
    "id",
    "created_at",
    "updated_at",
    "deleted_at",
}


def _apply_fk_metadata_to_field(
    field_cfg: Dict[str, Any],
    fk_info: Optional[Dict[str, str]],
) -> None:
    """
    Mutate a field config dict to include foreign key metadata.

    - is_foreign_key: bool
    - foreign_key_table: str | null
    - foreign_key_field: str | null

    Uses setdefault so it won't override manually customized values.
    """
    if not isinstance(field_cfg, dict):
        return

    if fk_info:
        field_cfg.setdefault("is_foreign_key", True)
        field_cfg.setdefault("foreign_key_table", fk_info.get("ref_table"))
        field_cfg.setdefault("foreign_key_field", fk_info.get("ref_column"))
    else:
        field_cfg.setdefault("is_foreign_key", False)
        field_cfg.setdefault("foreign_key_table", None)
        field_cfg.setdefault("foreign_key_field", None)


def build_field_config(
    column_name: str,
    fk_info: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Build a generic WizardFieldConfig-like dict for JSON output.

    Shape matches what wizard_config.py expects when loading:
      {
        "name": "...",
        "label": "...",
        "required": bool,
        "prompt": null or str,
        "summary_label": "...",
        "normalizer": null or "normalize_consent_status",
        "default_value": null or "today",
        "is_foreign_key": bool,
        "foreign_key_table": null or str,
        "foreign_key_field": null or str,
      }
    """
    label = column_name.replace("_", " ").title()
    required = column_name not in META_OPTIONAL_FIELDS

    cfg: Dict[str, Any] = {
        "name": column_name,
        "label": label,
        "required": required,
        "prompt": None,
        "summary_label": label,
        "normalizer": None,
        "default_value": None,
    }

    _apply_fk_metadata_to_field(cfg, fk_info)
    return cfg


def load_existing_wizard_configs() -> Dict[str, Any]:
    """
    Load existing wizard_configs.json if present, otherwise return a stub.
    """
    if not WIZARD_CONFIGS_PATH.exists():
        logger.info("wizard_configs.json not found; starting from empty config")
        return {"collections": {}}

    with WIZARD_CONFIGS_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        logger.warning("wizard_configs.json did not contain a dict root; resetting to empty")
        return {"collections": {}}

    data.setdefault("collections", {})
    if not isinstance(data["collections"], dict):
        logger.warning("wizard_configs.json['collections'] not a dict; resetting to empty")
        data["collections"] = {}

    return data


def merge_tables_into_configs(
    existing: Dict[str, Any],
    tables: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Merge parsed tables into the existing wizard config structure.

    - Preserve any existing collection configs (including prompts/normalizers).
    - For existing collections, add any missing fields and update FK metadata.
    - For new collections, create a generic config from the columns.
    """
    collections: Dict[str, Any] = dict(existing.get("collections", {}))

    for table_name, table_info in tables.items():
        if is_system_table(table_name):
            logger.info("Skipping system table: %s", table_name)
            continue

        columns: List[str] = list(table_info.get("columns") or [])
        foreign_keys: Dict[str, Dict[str, str]] = dict(table_info.get("foreign_keys") or {})

        if not columns:
            logger.info("Skipping table with no columns detected: %s", table_name)
            continue

        cfg = collections.get(table_name)

        if cfg is None:
            # New collection: build from scratch
            logger.info("Adding new wizard config for collection: %s", table_name)
            fields = [
                build_field_config(col, foreign_keys.get(col))
                for col in columns
            ]
            collections[table_name] = {
                "collection": table_name,
                "fields": fields,
            }
            continue

        # Existing collection: merge any new columns and update FK metadata
        logger.info("Merging columns into existing wizard config for collection: %s", table_name)
        existing_fields = cfg.setdefault("fields", [])
        existing_names_to_field: Dict[str, Dict[str, Any]] = {}

        for f in existing_fields:
            if isinstance(f, dict):
                name = f.get("name")
                if isinstance(name, str):
                    existing_names_to_field[name] = f

        # First, ensure FK metadata is present on all existing fields
        for col in columns:
            field_cfg = existing_names_to_field.get(col)
            if field_cfg is not None:
                _apply_fk_metadata_to_field(field_cfg, foreign_keys.get(col))

        # Then, add any missing fields
        existing_names = set(existing_names_to_field.keys())
        for col in columns:
            if col in existing_names:
                continue
            logger.info("  Adding missing field %r to collection %s", col, table_name)
            existing_fields.append(build_field_config(col, foreign_keys.get(col)))

    # Preserve any collections that have no corresponding table in DBML
    return {"collections": collections}


def main() -> None:
    if not DBML_PATH.exists():
        raise SystemExit(f"schema.dbml not found at {DBML_PATH}")

    logger.info("Reading DBML from %s", DBML_PATH)
    dbml_text = DBML_PATH.read_text(encoding="utf-8")

    tables = parse_dbml_tables(dbml_text)
    logger.info("Parsed %d tables from DBML", len(tables))

    existing = load_existing_wizard_configs()
    merged = merge_tables_into_configs(existing, tables)

    WIZARD_CONFIGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with WIZARD_CONFIGS_PATH.open("w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, sort_keys=True, ensure_ascii=False)

    logger.info("Updated wizard configs written to %s", WIZARD_CONFIGS_PATH)


if __name__ == "__main__":
    main()
