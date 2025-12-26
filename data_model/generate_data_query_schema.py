#!/usr/bin/env python
"""
Generate ../src/OSSS/ai/agents/data_query/schema.py
from schema.dbml located in the same directory as this script.

Features:
- UI-friendly tables only (skip obvious system/migration tables)
- Map fields (column name -> DB type)
- Infer relationships from foreign-key refs
- Handle composite PKs gracefully (choose a useful display field)
- Infer synonyms for NL mapping:
  - "created at" -> "created_at"
  - "person name" -> "person.full_name"
  - generic "name" -> "<rel>.<display_field>" when unambiguous
"""

from __future__ import annotations

import os
import textwrap
from dataclasses import dataclass, field
from typing import Dict, List

from pydbml import PyDBML  # pip install pydbml


# ---------------------------------------------------------------------------
# Internal helper representations
# ---------------------------------------------------------------------------

@dataclass
class RelationshipDef:
    name: str              # "person"
    local_field: str       # "person_id" (on base table)
    remote_collection: str # "persons"
    remote_key: str        # "id"
    display_field: str     # "full_name"


@dataclass
class CollectionSchemaDef:
    name: str
    fields: Dict[str, str] = field(default_factory=dict)
    relationships: Dict[str, RelationshipDef] = field(default_factory=dict)
    synonyms: Dict[str, str] = field(default_factory=dict)


DISPLAY_FIELD_CANDIDATES = [
    "full_name",
    "name",
    "display_name",
    "title",
    "code",
]


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------

def is_ui_friendly_table(table_name: str) -> bool:
    """
    Heuristic filter to avoid system / migration / internal tables.
    Adjust as needed for your environment.
    """
    n = table_name.lower()

    # Common "system-y" prefixes
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
    )
    if any(n.startswith(p) for p in system_prefixes):
        return False

    # Common log/migration suffixes
    system_suffixes = (
        "_migrations",
        "_log",
        "_logs",
        "_audit",
    )
    if any(n.endswith(s) for s in system_suffixes):
        return False

    return True


def choose_display_field(table) -> str:
    """
    Heuristically choose a human-friendly display field for a table.
    Prefers common 'name' columns; falls back to PK or first text-ish column.
    Composite PKs are handled by choosing the first PK column.
    """
    column_names = [col.name for col in table.columns]

    # 1) Preferred candidate names
    for candidate in DISPLAY_FIELD_CANDIDATES:
        if candidate in column_names:
            return candidate

    # 2) Primary key(s) – composite or single
    pk_cols = [col for col in table.columns if getattr(col, "pk", False)]
    if pk_cols:
        return pk_cols[0].name

    # 3) First "text-ish" column
    for col in table.columns:
        col_type = str(col.type).lower()
        if any(t in col_type for t in ("varchar", "text", "string", "char")):
            return col.name

    # 4) Fallback: first column, or "id"
    if column_names:
        return column_names[0]
    return "id"


def singularize(name: str) -> str:
    """
    Very naive singularization for relationship names:
    persons -> person, students -> student, categories -> category, etc.
    """
    n = name
    if n.endswith("ies"):
        return n[:-3] + "y"
    if n.endswith("s") and not n.endswith("ss"):
        return n[:-1]
    return n


# ---------------------------------------------------------------------------
# Synonym inference
# ---------------------------------------------------------------------------

def infer_synonyms_for_schema(schemas: Dict[str, CollectionSchemaDef]) -> None:
    """
    Populate .synonyms for each CollectionSchemaDef.

    Strategies:
    - Humanized column names: "created at" -> "created_at"
    - Relationship display synonyms: "person name" -> "person.full_name"
    - Generic "name" -> "<rel>.<display_field>" if only one 'name'-ish rel
    """
    for schema in schemas.values():
        # 1) Humanized column names
        for col, _ctype in schema.fields.items():
            if "_" in col:
                pretty = col.replace("_", " ")
                schema.synonyms.setdefault(pretty, col)

        # 2) Relationship-based synonyms
        name_rels = []
        for rel in schema.relationships.values():
            path = f"{rel.name}.{rel.display_field}"
            rel_name_lower = rel.name.lower()

            # "<entity> name" -> "entity.display_field"
            schema.synonyms.setdefault(f"{rel_name_lower} name", path)

            # Basic alias: "<entity>" -> "entity.display_field"
            schema.synonyms.setdefault(rel_name_lower, path)

            # Track "name-ish" display fields for possible generic 'name'
            if "name" in rel.display_field.lower():
                name_rels.append(rel)

        # 3) Generic "name" synonym when unambiguous
        if len(name_rels) == 1:
            only_rel = name_rels[0]
            path = f"{only_rel.name}.{only_rel.display_field}"
            schema.synonyms.setdefault("name", path)


# ---------------------------------------------------------------------------
# DBML → CollectionSchemaDef mapping
# ---------------------------------------------------------------------------

def load_schemas_from_dbml(dbml_path: str) -> Dict[str, CollectionSchemaDef]:
    """
    Parse the DBML file and build CollectionSchemaDef objects, one per UI-friendly table.

    We treat each foreign-key Ref as a relationship on the "local" (FK) side.
    Composite PKs/FKs are handled gracefully by using the first column pair.
    """
    with open(dbml_path, "r", encoding="utf-8") as f:
        dbml_text = f.read()

    db = PyDBML(dbml_text)

    # Filter and initialize schemas for UI-friendly tables
    schemas: Dict[str, CollectionSchemaDef] = {}
    tables_by_name = {}

    for table in db.tables:
        if not is_ui_friendly_table(table.name):
            continue

        fields = {col.name: str(col.type) for col in table.columns}
        schemas[table.name] = CollectionSchemaDef(
            name=table.name,
            fields=fields,
        )
        tables_by_name[table.name] = table

    # Build relationships from refs
    for ref in db.refs:
        endpoints = getattr(ref, "endpoints", getattr(ref, "ends", None))

        if not endpoints or len(endpoints) < 2:
            continue

        # Some DBMLs may use >2 endpoints for composite refs.
        # We'll treat the first local/remote pair as the "primary" relationship.
        # This keeps things simple while still being robust.
        # If you need full composite-key semantics, you'd extend RelationshipDef.
        local = endpoints[0]
        remote = endpoints[1]

        local_table_name = local.table.name
        remote_table_name = remote.table.name

        # Skip if either side is not UI-friendly / not in our schemas
        if local_table_name not in schemas or remote_table_name not in schemas:
            continue

        local_table = tables_by_name[local_table_name]
        remote_table = tables_by_name[remote_table_name]

        rel_name = singularize(remote_table_name)
        display_field = choose_display_field(remote_table)

        rel_def = RelationshipDef(
            name=rel_name,
            local_field=local.col.name,
            remote_collection=remote_table_name,
            remote_key=remote.col.name,
            display_field=display_field,
        )

        schemas[local_table_name].relationships[rel_name] = rel_def

    # Infer synonyms after relationships are known
    infer_synonyms_for_schema(schemas)

    return schemas


# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------

HEADER = '''\
# This file was auto-generated from a DBML schema.
# Do not edit by hand; instead, update schema.dbml and re-run the generator.

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class Relationship:
    name: str
    local_field: str
    remote_collection: str
    remote_key: str
    display_field: str  # e.g. "full_name"


@dataclass
class CollectionSchema:
    name: str
    fields: Dict[str, str]
    relationships: Dict[str, Relationship]
    synonyms: Dict[str, str]


SCHEMAS: Dict[str, CollectionSchema] = {
'''


def _emit_fields_block(fields: Dict[str, str], indent: int = 8) -> List[str]:
    lines: List[str] = []
    pad = " " * indent
    lines.append(pad + "fields={")
    for fname, ftype in sorted(fields.items()):
        lines.append(pad + f'    "{fname}": "{ftype}",')
    lines.append(pad + "},")
    return lines


def _emit_relationships_block(rels: Dict[str, RelationshipDef], indent: int = 8) -> List[str]:
    lines: List[str] = []
    pad = " " * indent
    lines.append(pad + "relationships={")
    for rel_name in sorted(rels.keys()):
        rel = rels[rel_name]
        block = f'''\
"{rel.name}": Relationship(
    name="{rel.name}",
    local_field="{rel.local_field}",
    remote_collection="{rel.remote_collection}",
    remote_key="{rel.remote_key}",
    display_field="{rel.display_field}",
),'''
        lines.append(textwrap.indent(block, pad + "    ").rstrip())
    lines.append(pad + "},")
    return lines


def _emit_synonyms_block(synonyms: Dict[str, str], indent: int = 8) -> List[str]:
    lines: List[str] = []
    pad = " " * indent
    lines.append(pad + "synonyms={")
    for key in sorted(synonyms.keys()):
        val = synonyms[key]
        lines.append(pad + f'    "{key}": "{val}",')
    lines.append(pad + "},")
    return lines


def generate_schema_py(schemas: Dict[str, CollectionSchemaDef]) -> str:
    """
    Generate the full Python source for schema.py as a string.
    """
    lines: List[str] = []
    lines.append(HEADER.rstrip("\n"))

    # Deterministic output
    for collection_name in sorted(schemas.keys()):
        schema = schemas[collection_name]

        lines.append(f'    "{schema.name}": CollectionSchema(')
        lines.append(f'        name="{schema.name}",')

        # fields
        lines.extend(_emit_fields_block(schema.fields, indent=8))

        # relationships
        lines.extend(_emit_relationships_block(schema.relationships, indent=8))

        # synonyms
        lines.extend(_emit_synonyms_block(schema.synonyms, indent=8))

        lines.append("    ),")

    lines.append("}")
    lines.append("")  # final newline
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI / entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dbml_path = os.path.join(script_dir, "schema.dbml")
    output_path = os.path.normpath(
        os.path.join(
            script_dir,
            "..",
            "src",
            "OSSS",
            "ai",
            "agents",
            "data_query",
            "schema.py",
        )
    )

    print(f"[gen] Reading DBML from: {dbml_path}")
    print(f"[gen] Writing schema to: {output_path}")

    schemas = load_schemas_from_dbml(dbml_path)
    content = generate_schema_py(schemas)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("[gen] Done — schema.py generated successfully.")


if __name__ == "__main__":
    main()
