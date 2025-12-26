#!/usr/bin/env python3

"""
Generate ../src/OSSS/ai/agents/data_query/query_metadata.py
from schema.dbml located in the same directory as this script.

This produces DEFAULT_QUERY_SPECS based on foreign key relationships,
column listings extracted from DBML, and merges in synonyms from schema.py.
"""

from __future__ import annotations

import os
import sys
import textwrap
from dataclasses import dataclass, field
from typing import Dict, List

from pydbml import PyDBML  # pip install pydbml


# ---------------------------------------------------------------------------
# Internal defs for generation
# ---------------------------------------------------------------------------

@dataclass
class ColumnDef:
    name: str
    col_type: str
    is_pk: bool = False


@dataclass
class JoinDef:
    from_collection: str
    from_field: str
    to_collection: str
    to_field: str
    alias: str  # "person"


@dataclass
class TableDef:
    name: str
    columns: List[ColumnDef] = field(default_factory=list)
    joins: List[JoinDef] = field(default_factory=list)
    search_fields: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers: naming & filtering
# ---------------------------------------------------------------------------
# Per-table UI default overrides: aliases you want by default.
# Keys are table names from DBML / collection names.
UI_DEFAULT_OVERRIDES: Dict[str, List[str]] = {
    # example: for consents, show the user-friendly fields by default
    "consents": ["person_name", "consent_type", "granted", "effective_date"],
    # add more here as needed
}


PREFERRED_UI_FIELDS_ORDER = [
    "id",
    "code",
    "name",
    "full_name",
    "first_name",
    "last_name",
    "email",
    "phone",
    "status",
    "type",
    "category",
    "created_at",
    "updated_at",
]


def pick_ui_default_aliases(table: TableDef, max_fields: int = 5) -> List[str]:
    """
    Choose a small, UI-friendly subset of fields for this table.

    Heuristic:
      1) Take common "nice" fields in a fixed preference order.
      2) If none match, just fall back to the first few columns.
    """
    cols = [c.name for c in table.columns]
    chosen: List[str] = []

    # 1) Preferred names in a stable order
    for name in PREFERRED_UI_FIELDS_ORDER:
        if name in cols and name not in chosen:
            chosen.append(name)
        if len(chosen) >= max_fields:
            break

    # 2) Fallback: first N columns
    if not chosen:
        chosen = cols[:max_fields]

    return chosen

def singularize(name: str) -> str:
    """
    Basic plural → singular logic for aliasing joins
    persons → person
    consents → consent
    categories → category
    """
    if name.endswith("ies"):
        return name[:-3] + "y"
    if name.endswith("s") and not name.endswith("ss"):
        return name[:-1]
    return name


def is_ui_friendly_table(table_name: str) -> bool:
    """
    Heuristic filter to avoid system / migration / internal tables.
    Should stay in sync with schema.py generator.
    """
    n = table_name.lower()

    system_prefixes = (
        "_",
        "alembic_",
        "django_",
        "auth_",
        "pg_",
        "sqlalchemy_",
        "flyway_",
        "migrations",
        "applied_migrations",
        "sys_",
    )
    if any(n.startswith(p) for p in system_prefixes):
        return False

    system_suffixes = (
        "_migrations",
        "_log",
        "_logs",
        "_audit",
    )
    if any(n.endswith(s) for s in system_suffixes):
        return False

    return True


def infer_search_fields(table) -> List[str]:
    """
    Pick good search fields for a given DBML table.

    Strategy:
      - Prefer columns whose names include 'name', 'email', 'code', 'number'
      - Prefer text-ish types for generic search
      - Fallback to first few text-ish columns
    """
    name_like_cols: List[str] = []
    text_like_cols: List[str] = []

    for col in table.columns:
        col_name = col.name.lower()
        col_type = str(col.type).lower()

        if any(k in col_name for k in ("name", "email", "code", "number")):
            name_like_cols.append(col.name)

        if any(t in col_type for t in ("varchar", "text", "string", "char")):
            text_like_cols.append(col.name)

    if name_like_cols:
        return name_like_cols

    # fallback: first 3 text-like columns
    return text_like_cols[:3]


# ---------------------------------------------------------------------------
# Load DBML and extract structure
# ---------------------------------------------------------------------------

def load_tables_from_dbml(dbml_path: str) -> Dict[str, TableDef]:
    with open(dbml_path, "r", encoding="utf-8") as f:
        dbml_text = f.read()

    db = PyDBML(dbml_text)

    tables: Dict[str, TableDef] = {}

    # Tables & columns
    for table in db.tables:
        if not is_ui_friendly_table(table.name):
            continue

        tdef = TableDef(
            name=table.name,
            columns=[
                ColumnDef(
                    name=col.name,
                    col_type=str(col.type),
                    is_pk=getattr(col, "pk", False),
                )
                for col in table.columns
            ],
            search_fields=infer_search_fields(table),
        )
        tables[table.name] = tdef

    # Joins from refs / foreign keys
    for ref in db.refs:
        endpoints = getattr(ref, "endpoints", getattr(ref, "ends", None))
        if not endpoints or len(endpoints) != 2:
            continue

        local, remote = endpoints

        from_table = local.table.name
        to_table = remote.table.name

        if from_table not in tables or to_table not in tables:
            continue

        alias = singularize(to_table)

        tables[from_table].joins.append(
            JoinDef(
                from_collection=from_table,
                from_field=local.col.name,
                to_collection=to_table,
                to_field=remote.col.name,
                alias=alias,
            )
        )

    return tables


# ---------------------------------------------------------------------------
# Generate python code
# ---------------------------------------------------------------------------

FILE_HEADER = '''\
# AUTO-GENERATED FILE — DO NOT EDIT
# Generated from schema.dbml by generate_query_metadata.py

from OSSS.ai.agents.data_query.queryspec import Projection, Join, QuerySpec


DEFAULT_QUERY_SPECS = {
'''


MAX_DEFAULT_PROJECTIONS = 10


def _pick_default_projection_fields(table_def: TableDef) -> List[str]:
    """
    Auto-pick a small default subset when there are many columns.

    Priority:
      1) Primary keys
      2) *name-like* columns
      3) FKs (columns ending in '_id')
      4) created_at / updated_at / status
    """
    cols = table_def.columns
    if len(cols) <= MAX_DEFAULT_PROJECTIONS:
        return [c.name for c in cols]

    pks = [c.name for c in cols if c.is_pk]
    name_like = [c.name for c in cols if "name" in c.name.lower()]
    fks = [c.name for c in cols if c.name.lower().endswith("_id")]
    meta = [
        c.name
        for c in cols
        if c.name in ("created_at", "updated_at", "status", "state")
    ]

    ordered: List[str] = []
    for group in (pks, name_like, fks, meta):
        for col_name in group:
            if col_name not in ordered:
                ordered.append(col_name)

    # If still not enough, fill with remaining columns in order
    if len(ordered) < MAX_DEFAULT_PROJECTIONS:
        for c in cols:
            if c.name not in ordered:
                ordered.append(c.name)
            if len(ordered) >= MAX_DEFAULT_PROJECTIONS:
                break

    return ordered[:MAX_DEFAULT_PROJECTIONS]


def generate_query_metadata_py(
    tables: Dict[str, TableDef],
    synonyms_by_collection: Dict[str, List[str]] | None = None,
) -> str:

    lines: List[str] = [FILE_HEADER.rstrip("\n")]

    for table_name in sorted(tables.keys()):
        t = tables[table_name]

        lines.append(f'    "{t.name}": QuerySpec(')
        lines.append(f'        base_collection="{t.name}",')
        lines.append("        projections=[")

        # default: project all columns on base collection
        for col in t.columns:
            block = f'Projection("{t.name}", "{col.name}"),'
            lines.append(" " * 12 + block)

        lines.append("        ],")
        lines.append("        joins=[")

        # default joins based on DBML refs
        for j in t.joins:
            block = f'''\
Join(
    from_collection="{j.from_collection}",
    from_field="{j.from_field}",
    to_collection="{j.to_collection}",
    to_field="{j.to_field}",
    alias="{j.alias}",
),'''
            lines.append(textwrap.indent(block, " " * 12).rstrip())

        lines.append("        ],")

        # 👇 NEW: tiny UI default subset, with per-table overrides
        override = UI_DEFAULT_OVERRIDES.get(t.name)
        if override:
            ui_aliases = override
        else:
            ui_aliases = pick_ui_default_aliases(t)

        if ui_aliases:
            lines.append(f"        ui_default_projection_aliases={ui_aliases!r},")

        lines.append("    ),")

    lines.append("}")
    lines.append("")  # final newline
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # ⇣ read schema.dbml from SAME DIRECTORY
    dbml_path = os.path.join(script_dir, "schema.dbml")

    # Ensure src/ is importable so we can import schema.SCHEMAS
    project_root = os.path.normpath(os.path.join(script_dir, ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Import the generated schema (must be generated first)
    from OSSS.ai.agents.data_query.schema import SCHEMAS  # type: ignore

    # ⇣ write to ../src/OSSS/ai/agents/data_query/query_metadata.py
    output_path = os.path.normpath(
        os.path.join(
            script_dir,
            "..",
            "src",
            "OSSS",
            "ai",
            "agents",
            "data_query",
            "query_metadata.py",
        )
    )

    print(f"[gen] Reading DBML from: {dbml_path}")
    print(f"[gen] Loading SCHEMAS from: OSSS.ai.agents.data_query.schema")
    print(f"[gen] Writing query metadata to: {output_path}")

    tables = load_tables_from_dbml(dbml_path)

    # Merge schema.synonyms into DEFAULT_QUERY_SPECS
    synonyms_by_collection: Dict[str, Dict[str, str]] = {
        name: cs.synonyms for name, cs in SCHEMAS.items()
    }

    content = generate_query_metadata_py(tables, synonyms_by_collection)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("[gen] Done — query_metadata.py generated successfully.")


if __name__ == "__main__":
    main()
