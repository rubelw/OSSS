#!/usr/bin/env python3

# /data_models/generate_wizard_configs.py
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any

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


def parse_dbml_tables(dbml_text: str) -> Dict[str, List[str]]:
    """
    Return {table_name: [column_name, ...]} parsed from DBML.

    We keep this intentionally lightweight and conservative:
    - Only treat lines that look like "column_name type ..." as columns.
    - Skip Notes, Indexes, Refs, etc.
    """
    tables: Dict[str, List[str]] = {}

    for m in TABLE_PATTERN.finditer(dbml_text):
        table_name = m.group("name")
        body = m.group("body")

        cols: List[str] = []
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
            if mcol:
                cols.append(mcol.group("col"))

        tables[table_name] = cols

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


def build_field_config(column_name: str) -> Dict[str, Any]:
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
      }
    """
    label = column_name.replace("_", " ").title()
    required = column_name not in META_OPTIONAL_FIELDS

    return {
        "name": column_name,
        "label": label,
        "required": required,
        "prompt": None,
        "summary_label": label,
        "normalizer": None,
        "default_value": None,
    }


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
    tables: Dict[str, List[str]],
) -> Dict[str, Any]:
    """
    Merge parsed tables into the existing wizard config structure.

    - Preserve any existing collection configs (including prompts/normalizers).
    - For existing collections, add any missing fields.
    - For new collections, create a generic config from the columns.
    """
    collections: Dict[str, Any] = dict(existing.get("collections", {}))

    for table_name, columns in tables.items():
        if is_system_table(table_name):
            logger.info("Skipping system table: %s", table_name)
            continue

        if not columns:
            logger.info("Skipping table with no columns detected: %s", table_name)
            continue

        cfg = collections.get(table_name)

        if cfg is None:
            # New collection: build from scratch
            logger.info("Adding new wizard config for collection: %s", table_name)
            fields = [build_field_config(col) for col in columns]
            collections[table_name] = {
                "collection": table_name,
                "fields": fields,
            }
            continue

        # Existing collection: merge any new columns
        logger.info("Merging columns into existing wizard config for collection: %s", table_name)
        existing_fields = cfg.setdefault("fields", [])
        existing_names = {f.get("name") for f in existing_fields if isinstance(f, dict)}

        for col in columns:
            if col in existing_names:
                continue
            logger.info("  Adding missing field %r to collection %s", col, table_name)
            existing_fields.append(build_field_config(col))

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
