#!/usr/bin/env python3
"""
Deterministic CSV generator from DBML.

Key features:
- Uses DBML ONLY for tables/columns (no FK trust).
- ALL FK relationships are manually defined in MANUAL_FK_MAP.
- Deterministic UUIDs for ALL ID columns.
- Deterministic FK assignment for child tables.
- SCC-aware topological sorting so FK parents are generated before children.
- Handles cycles (including self-FKs) by generating SCCs as batches.
- Defensive behavior:
  - Optional relaxed FK enforcement for selected tables.
  - Optional skip-data tables.
  - On hard FK errors, writes EMPTY CSVs for affected tables instead of crashing.

Script location:
  seed_csvs/seed_from_dbml.py
  seed_csvs/schema.dbml
  csv/ (sibling of seed_csvs) will contain generated CSVs + fk_graph.dot

NEW:
- If a CSV for a table exists in ../raw_data/<table>.csv, use that as the
  base data for that table (normalized to the schema) instead of generating
  synthetic rows. If no such file exists, fall back to sample values.
- For any UUID-like column (uuid type, char(36), 'id', or '*_id'), if the
  raw value does NOT look like a UUID, it is replaced with a deterministic
  UUID so Postgres stays happy.
"""

from __future__ import annotations
import argparse
import csv
import datetime
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Sequence, Any

from manual_fk_map import MANUAL_FK_MAP

# ------------------------------------------------------------
# Configuration knobs
# ------------------------------------------------------------

# Tables where we DO generate data, but DO NOT enforce FKs.
# FK columns will be left blank ("") when they cannot be safely filled.
RELAX_FK_TABLES: Set[str] = set()

# Per-column FK relax: only these FK columns are blanked/ignored for seeds.
RELAX_FK_COLUMNS: Set[Tuple[str, str]] = {
    ("documents", "current_version_id"),
    # add more if needed later, e.g.:
    # ("proposals", "curriculum_id"),
}

# Tables where we ONLY write headers (no data rows).
SKIP_DATA_TABLES: Set[str] = {
    "paychecks",

}

# For these (table, column), try to use a distinct parent row per child row
# instead of always the first parent row.
UNIQUE_FK_PER_ROW: Set[Tuple[str, str]] = {
    ("students", "person_id"),
    # Option B: spread students/teachers across different user_profiles
    ("course_students", "user_id"),
    ("course_teachers", "user_id"),
    # add more if you hit similar unique FK issues, e.g.:
    # ("user_accounts", "person_id"),
}

# For enum-typed columns, provide a list of allowed values so we can
# generate something valid instead of nonsense.
ENUM_OVERRIDES: Dict[Tuple[str, str], List[str]] = {
    # Adjust these to match your actual enum values:
    ("courses", "course_state"): ["PROVISIONED", "ACTIVE", "ARCHIVED", 'DECLINED', 'SUSPENDED'],
    ("guardian_invitations", "state"): ["PENDING", "COMPLETE"],
    ("announcements", "state"): ["PUBLISHED", "DRAFT", "SCHEDULED"],
    ("coursework", "work_type"): [
        "ASSIGNMENT", "SHORT_ANSWER_QUESTION",
        "MULTIPLE_CHOICE_QUESTION", "MATERIAL",
    ],
    ("coursework", "state"): [
        "PUBLISHED",
        "DRAFT",
        "SCHEDULED",
    ],
    ("curricula", "status"): [
        "draft",
        "adopted",
        "retired",
    ],
    ("materials", "type"): [
        "DRIVE_FILE",
        "YOUTUBE",
        "LINK",
        "FORM"
    ],
    ("student_submissions", "state"): [
        "NEW",
        "CREATED",
        "TURNED_IN",
        "RETURNED",
        "RECLAIMED_BY_STUDENT"
    ],
    ("proposals", "status"): [
        "draft",
        "submitted",
        "in_review",
        "approved",
        "rejected"
    ],
    ("review_rounds", "status"): [
        "open",
        "closed",
        "canceled"
    ],
    ("approvals", "status"): [
        "active",
        "expired",
        "revoked"
    ],
    ("round_decisions", "decision"): [
        "approved",
        "approved_with_conditions",
        "revisions_requested",
        "rejected",
    ],
    ("reviews", "status"): [
        "draft",
        "submitted"
    ]
}


def is_relaxed_fk_column(table: str, column: str) -> bool:
    """
    Return True if this FK column should be 'relaxed' for seed data:
    - Either the whole table is relaxed (RELAX_FK_TABLES), or
    - The specific (table, column) pair is in RELAX_FK_COLUMNS.
    """
    return table in RELAX_FK_TABLES or (table, column) in RELAX_FK_COLUMNS


# ------------------------------------------------------------
# Regex
# ------------------------------------------------------------

UUID_CHAR_PATTERN = re.compile(r"char\s*\(\s*36\s*\)", re.I)
STRING_LEN_RE = re.compile(r"\(\s*(\d+)\s*\)")

TABLE_START_RE = re.compile(r"^\s*Table\s+`?([\w]+)`?\s*{")
COLUMN_RE = re.compile(r"^\s*`?(\w+)`?\s+([^\s\[]+)(.*)$")
# We still allow 'Ref' lines in DBML but we IGNORE them for FKs.
REF_RE = re.compile(
    r"Ref\s*:\s*`?(\w+)`?\.(\w+)\s*>\s*`?(\w+)`?\.(\w+)",
    re.IGNORECASE,
)

# NEW: simple UUID pattern for validating raw string UUIDs
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}$"
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
# DBML Parsing (tables + columns ONLY)
# ------------------------------------------------------------

def parse_dbml(dbml_path: Path) -> Dict[str, Table]:
    """
    Parse DBML for tables + columns only.
    Ref lines are ignored; FK wiring comes from MANUAL_FK_MAP.
    """
    text = dbml_path.read_text()
    lines = text.splitlines()

    tables: Dict[str, Table] = {}
    current_table: Optional[Table] = None

    for raw in lines:
        line = raw.strip()

        # Ignore Ref lines; we don't trust DBML FKs
        if line.startswith("Ref"):
            continue

        # Start table
        m_table = TABLE_START_RE.match(raw)
        if m_table:
            name = m_table.group(1)
            current_table = Table(name=name)
            tables[name] = current_table
            continue

        # End table
        if current_table and line.startswith("}"):
            current_table = None
            continue

        # Column
        if current_table and raw and not raw.strip().startswith(("Indexes", "Note")):
            no_comment = raw.split("//")[0].rstrip()
            m = COLUMN_RE.match(no_comment)
            if m:
                col_name, col_type, rest = m.groups()
                is_pk = "pk" in rest
                current_table.columns.append(Column(col_name, col_type.lower(), is_pk))

    return tables

def dedupe_unit_standard_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    For unit_standard_map, enforce uniqueness on (unit_id, standard_id).
    """
    seen: Set[Tuple[Optional[str], Optional[str]]] = set()
    out: List[Dict[str, str]] = []

    for r in rows:
        key = (r.get("unit_id"), r.get("standard_id"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)

    return out


def print_tables_without_fk_map(tables: Dict[str, Table]) -> None:
    """
    Print tables that have NO entry in MANUAL_FK_MAP
    (i.e., no outgoing manual FKs defined for them).
    """
    mapped_children = set(MANUAL_FK_MAP.keys())
    all_tables = set(tables.keys())

    missing = sorted(all_tables - mapped_children)

    print("\n=== Tables without manual FK map (no MANUAL_FK_MAP entry) ===")
    for name in missing:
        print(f"  - {name}")
    print("=== End missing FK map tables ===\n")


# ------------------------------------------------------------
# Manual FK binding
# ------------------------------------------------------------

def build_manual_fk_list(tables: Dict[str, Table]) -> List[ForeignKey]:
    """
    Build a list of ForeignKey objects from MANUAL_FK_MAP.
    Only includes FKs where both child + parent tables exist in DBML.
    """
    fks: List[ForeignKey] = []
    for child_table, col_map in MANUAL_FK_MAP.items():
        if child_table not in tables:
            print(f"[WARN] MANUAL_FK_MAP references missing child table '{child_table}'")
            continue
        for child_col, (parent_table, parent_col) in col_map.items():
            if parent_table not in tables:
                print(
                    f"[WARN] MANUAL_FK_MAP {child_table}.{child_col} → "
                    f"{parent_table}.{parent_col}: parent table missing in DBML"
                )
                continue
            fks.append(
                ForeignKey(
                    child_table=child_table,
                    child_column=child_col,
                    parent_table=parent_table,
                    parent_column=parent_col,
                )
            )
    return fks


def bind_manual_fks_to_tables(
    tables: Dict[str, Table],
    fks: List[ForeignKey],
) -> None:
    """
    Populate Table.fks_out and Table.fks_in from MANUAL FKs.
    """
    for fk in fks:
        child = tables.get(fk.child_table)
        parent = tables.get(fk.parent_table)
        if not child or not parent:
            continue
        child.fks_out.append(fk)
        parent.fks_in.append(fk)


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def get_enum_value(table: str, col: Column, index: int) -> Optional[str]:
    options = ENUM_OVERRIDES.get((table, col.name))
    if not options:
        return None
    # deterministic cycle through options
    return options[(index - 1) % len(options)]


def get_fk_column_map(table_name: str, tables: Dict[str, Table]) -> Dict[str, Tuple[str, str]]:
    """
    Map child_column -> (parent_table, parent_column) for this table,
    using ONLY the manually bound FKs (Table.fks_out).
    """
    t = tables[table_name]
    return {fk.child_column: (fk.parent_table, fk.parent_column) for fk in t.fks_out}


def get_fk_parent_tables(table_name: str, tables: Dict[str, Table]) -> List[str]:
    t = tables.get(table_name)
    if not t:
        return []
    return sorted({fk.parent_table for fk in t.fks_out})


def has_self_fk(table_name: str, tables: Dict[str, Table]) -> bool:
    t = tables.get(table_name)
    if not t:
        return False
    return any(fk.parent_table == table_name for fk in t.fks_out)


# ------------------------------------------------------------
# SCC & Component Ordering
# ------------------------------------------------------------

def build_dependency_graph(tables: Dict[str, Table], fks: List[ForeignKey]) -> Dict[str, Set[str]]:
    """
    deps[table] = set(parent_tables it depends on)
    """
    deps: Dict[str, Set[str]] = {name: set() for name in tables}
    for fk in fks:
        if fk.child_table in deps and fk.parent_table in deps:
            deps[fk.child_table].add(fk.parent_table)
    return deps

def dedupe_by_keys(rows: List[Dict[str, Any]], keys: Sequence[str]) -> List[Dict[str, Any]]:
    """
    Return a new list with at most one row per key combination.

    Keeps the *last* row for each key combo (useful if later rows have 'final' state),
    but you can invert the order if you prefer the first.
    """
    seen = set()
    deduped: List[Dict[str, Any]] = []

    # iterate reversed so we keep the last one we see
    for row in reversed(rows):
        key = tuple(row.get(k) for k in keys)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    deduped.reverse()
    return deduped

def dedupe_tutor_spec(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # One row per tutor_id
    return dedupe_by_keys(rows, ["tutor_id"])


def dedupe_student_submissions(rows: list[dict]) -> list[dict]:
    """Ensure at most one row per (student_user_id, coursework_id)."""
    seen: set[tuple[str, str]] = set()
    deduped: list[dict] = []

    # If you want to keep the *last* state (e.g. RETURNED), iterate reversed.
    for row in reversed(rows):
        key = (row.get("student_user_id"), row.get("coursework_id"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    # Reverse back to original order if you iterated reversed
    deduped.reverse()
    return deduped


def strongly_connected_components(deps: Dict[str, Set[str]]) -> List[List[str]]:
    """
    Tarjan's algorithm for SCCs.
    Returns list of components, each a list of table names.
    """
    index = 0
    indices: Dict[str, int] = {}
    lowlink: Dict[str, int] = {}
    stack: List[str] = []
    onstack: Set[str] = set()
    result: List[List[str]] = []

    def strongconnect(v: str) -> None:
        nonlocal index
        indices[v] = index
        lowlink[v] = index
        index += 1
        stack.append(v)
        onstack.add(v)

        for w in deps[v]:
            if w not in indices:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in onstack:
                lowlink[v] = min(lowlink[v], indices[w])

        if lowlink[v] == indices[v]:
            comp: List[str] = []
            while True:
                w = stack.pop()
                onstack.remove(w)
                comp.append(w)
                if w == v:
                    break
            result.append(comp)

    for v in deps.keys():
        if v not in indices:
            strongconnect(v)

    return result


def compute_components_and_order(
    tables: Dict[str, Table],
    fks: List[ForeignKey],
) -> Tuple[List[List[str]], Dict[str, int]]:
    """
    - Computes SCCs over FK dependency graph.
    - Builds a DAG of components with edges parent_comp -> child_comp.
    - Returns (ordered_components, table_to_component_index).
    """
    deps = build_dependency_graph(tables, fks)
    sccs = strongly_connected_components(deps)

    # Map table -> component index
    table_to_comp: Dict[str, int] = {}
    for idx, comp in enumerate(sccs):
        for t in comp:
            table_to_comp[t] = idx

    # Component DAG
    comp_adj: Dict[int, Set[int]] = {i: set() for i in range(len(sccs))}
    comp_indeg: Dict[int, int] = {i: 0 for i in range(len(sccs))}

    for fk in fks:
        if fk.child_table not in table_to_comp or fk.parent_table not in table_to_comp:
            continue
        c_child = table_to_comp[fk.child_table]
        c_parent = table_to_comp[fk.parent_table]
        if c_child != c_parent:
            if c_child not in comp_adj[c_parent]:
                comp_adj[c_parent].add(c_child)
                comp_indeg[c_child] += 1

    # Topo sort components (parents -> children)
    ready = sorted([cid for cid, deg in comp_indeg.items() if deg == 0])
    ordered_comp_ids: List[int] = []

    while ready:
        cid = ready.pop(0)
        ordered_comp_ids.append(cid)
        for nbr in sorted(comp_adj[cid]):
            comp_indeg[nbr] -= 1
            if comp_indeg[nbr] == 0:
                ready.append(nbr)
                ready.sort()

    # Safety: append any missing (shouldn't happen in a DAG)
    for cid in range(len(sccs)):
        if cid not in ordered_comp_ids:
            ordered_comp_ids.append(cid)

    ordered_components: List[List[str]] = []
    for cid in ordered_comp_ids:
        # Sort within SCC for deterministic order
        ordered_components.append(sorted(sccs[cid]))

    return ordered_components, table_to_comp


# ------------------------------------------------------------
# Deterministic ID Generator
# ------------------------------------------------------------

UUID_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000001")

def deterministic_uuid(table: str, column: str, index: int) -> str:
    key = f"{table}:{column}:{index}"
    return str(uuid.uuid5(UUID_NAMESPACE, key))


# ------------------------------------------------------------
# UUID helpers for raw-data coercion
# ------------------------------------------------------------

def looks_like_uuid(value: str) -> bool:
    """
    Return True if the given string looks like a UUID.
    """
    if not value:
        return False
    return bool(UUID_RE.match(value.strip()))


def coerce_uuid_from_raw(table: str, col: Column, raw_value: str, index: int) -> str:
    """
    If raw_value is a valid UUID string, keep it.
    Otherwise, generate a deterministic UUID for this table/column/index.
    """
    if raw_value and looks_like_uuid(raw_value):
        return raw_value.strip()
    return deterministic_uuid(table, col.name, index)


# ------------------------------------------------------------
# Fake Value Generator (deterministic except IDs)
# ------------------------------------------------------------

def get_string_length(type_str: str) -> Optional[int]:
    m = STRING_LEN_RE.search(type_str)
    return int(m.group(1)) if m else None

def patch_fk_all(
    generated: Dict[str, List[Dict[str, str]]],
    child_table: str,
    child_column: str,
    parent_table: str,
    parent_column: str = "id",
) -> None:
    """
    Post-process helper: ensure every child_table.child_column value points
    at a *real* parent_table.parent_column value.

    - Builds a list of valid parent IDs.
    - For each child row:
        * If child FK is already a valid parent ID, keep it.
        * Otherwise, deterministically remap that original value to one of the
          parent IDs (stable per distinct original value).
    """
    child_rows = generated.get(child_table)
    parent_rows = generated.get(parent_table)

    if not child_rows:
        print(
            f"[patch_fk_all] No rows for child table '{child_table}' – "
            f"nothing to patch."
        )
        return

    if not parent_rows:
        print(
            f"[patch_fk_all] No rows for parent table '{parent_table}' – "
            f"cannot patch {child_table}.{child_column}."
        )
        return

    # Collect valid parent IDs
    valid_parent_ids: List[str] = [
        str(r[parent_column])
        for r in parent_rows
        if parent_column in r and r[parent_column] not in (None, "")
    ]

    if not valid_parent_ids:
        print(
            f"[patch_fk_all] Parent table '{parent_table}' has no usable "
            f"'{parent_column}' values – skipping."
        )
        return

    mapping: Dict[str, str] = {}
    next_idx = 0

    for row in child_rows:
        orig = row.get(child_column)

        # If it's already a valid parent ID, leave it alone
        if orig in valid_parent_ids:
            continue

        # Treat None/empty as "needs an ID"
        key = orig or f"__missing__:{next_idx}"

        if key in mapping:
            row[child_column] = mapping[key]
            continue

        # Deterministically pick a parent row (round-robin)
        new_val = valid_parent_ids[next_idx % len(valid_parent_ids)]
        mapping[key] = new_val
        row[child_column] = new_val
        next_idx += 1

    print(
        f"[patch_fk_all] Patched {child_table}.{child_column} → "
        f"{parent_table}.{parent_column} for {len(child_rows)} row(s) "
        f"(distinct original values={len(mapping)})."
    )


def is_uuid_col(col: Column) -> bool:
    """
    Treat a column as UUID-backed only if its *type* is UUID-like,
    not just because its name ends with `_id`.

    This avoids generating UUID strings for integer FKs like school_id.
    """
    t = col.type.lower()

    # True UUID type
    if "uuid" in t:
        return True

    # Optional: plain char(36) as UUID
    if UUID_CHAR_PATTERN.fullmatch(t):
        return True

    # You can add more patterns here if you actually store UUIDs
    # in varchar(36) or similar.

    return False


def generate_deterministic_value(table: str, col: Column, index: int) -> str:
    # 1) Enum overrides: choose a single valid label
    override_key = (table, col.name)
    if override_key in ENUM_OVERRIDES:
        candidates = ENUM_OVERRIDES[override_key]
        # deterministic: cycle through the list by index
        return candidates[(index - 1) % len(candidates)]

    t = col.type

    if is_uuid_col(col):
        return deterministic_uuid(table, col.name, index)

    if "int" in t or "serial" in t:
        return str(index)

    if "numeric" in t or "decimal" in t:
        return str(index)

    if "bool" in t:
        return "true" if index % 2 == 0 else "false"

    if "date" in t and "time" not in t:
        return (datetime.date(2024, 1, 1) + datetime.timedelta(days=index)).isoformat()

    if "timestamp" in t:
        return (
            datetime.datetime(2024, 1, 1) +
            datetime.timedelta(hours=index)
        ).isoformat() + "Z"

    if "time" in t:
        h = 8 + (index % 10)
        m = (index * 7) % 60
        return f"{h:02d}:{m:02d}:00"

    if "json" in t:
        return "{}"

    if "char" in t or "text" in t or "varchar" in t:
        maxlen = get_string_length(t)
        value = f"{table}_{col.name}_{index}"
        return value[:maxlen] if maxlen else value

    return f"{table}_{col.name}_{index}"


# ------------------------------------------------------------
# Raw-data loader
# ------------------------------------------------------------

def load_raw_rows_for_table(
    table_name: str,
    tables: Dict[str, Table],
    raw_dir: Path,
) -> Optional[List[Dict[str, str]]]:
    """
    If ../raw_data/<table_name>.csv exists, load it and normalize to the table's schema:
    - Only keep columns defined in the DBML for this table.
    - For missing columns, fill with deterministic values.
    - For type-mismatched numeric columns, coerce or fall back to deterministic values.
    """
    csv_path = raw_dir / f"{table_name}.csv"
    if not csv_path.exists():
        return None

    table = tables[table_name]
    rows_out: List[Dict[str, str]] = []

    with csv_path.open("r", newline="", encoding="utf8") as f:
        reader = csv.DictReader(f)
        for i, raw in enumerate(reader, start=1):
            row: Dict[str, str] = {}
            for col in table.columns:
                raw_val = raw.get(col.name)

                if raw_val not in (None, ""):
                    # UUID-typed columns: coerce any non-UUID raw value
                    # into a deterministic UUID so Postgres is happy.
                    if is_uuid_col(col):
                        row[col.name] = coerce_uuid_from_raw(
                            table_name, col, str(raw_val), i
                        )

                    # Numeric columns: be forgiving (e.g. 'v1.2' -> '1' or '12')
                    elif is_int_type(col.type):
                        s = str(raw_val).strip()
                        # Extract digits from things like "v1.1", "v2", etc.
                        digits = "".join(ch for ch in s if ch.isdigit())
                        if digits:
                            row[col.name] = digits
                        else:
                            # No usable digits – fall back to deterministic
                            row[col.name] = generate_deterministic_value(
                                table_name, col, i
                            )
                    else:
                        # Non-numeric, non-UUID – just string-ify
                        row[col.name] = str(raw_val)
                else:
                    # Missing in raw – fill deterministically
                    row[col.name] = generate_deterministic_value(table_name, col, i)

            rows_out.append(row)

    print(f"  [raw_data] Using {len(rows_out)} row(s) from {csv_path} for {table_name}")
    return rows_out


# ------------------------------------------------------------
# Low-level CSV writer (supports "empty" CSVs)
# ------------------------------------------------------------

def write_csv_for_table(
    table_name: str,
    tables: Dict[str, Table],
    out_dir: Path,
    rows: List[Dict[str, str]],
) -> None:
    table = tables[table_name]
    csv_path = out_dir / f"{table_name}.csv"
    fieldnames = [c.name for c in table.columns]

    # 🔹 Dedupe just for unit_standard_map
    if table_name == "unit_standard_map" and rows:
        rows = dedupe_unit_standard_rows(rows)


    if table_name == "student_submissions":
        rows = dedupe_student_submissions(rows)

    if table_name == "tutor_spec":
        rows = dedupe_by_keys(rows, ["tutor_id"])

    if table_name == "meeting_publications":
        # PK is meeting_id, so ensure only one publication row per meeting
        rows = dedupe_by_keys(rows, ["meeting_id"])

    if table_name == "meeting_search_index":
        # PK is meeting_id: only one search_index row per meeting_allowed
        rows = dedupe_by_keys(rows, ["meeting_id"])

    if table_name == "plan_search_index":
        # PK is meeting_id: only one search_index row per meeting_allowed
        rows = dedupe_by_keys(rows, ["plan_id"])

    if table_name == "policy_search_index":
        # PK is meeting_id: only one search_index row per meeting_allowed
        rows = dedupe_by_keys(rows, ["policy_id"])

    if table_name == "policy_publications":
        # PK is policy_version_id, so only one publication row per version
        rows = dedupe_by_keys(rows, ["policy_version_id"])

    if table_name == "document_search_index":
        # PK is meeting_id: only one search_index row per meeting_allowed
        rows = dedupe_by_keys(rows, ["document_id"])

    if table_name == "maintenance_requests":
        # For seed data, we don't want broken FKs to work_orders.
        # Make all requests "not converted" by nulling out the FK.
        for row in rows:
            # Use empty string so CSV has a column value but Alembic/psycopg see NULL
            row["converted_work_order_id"] = ""

    if table_name == "work_order_parts":
        # For seed data, don't enforce parts FK.
        # Null out part_id so FK constraint does not fire.
        for row in rows:
            row["part_id"] = ""

    if table_name == "part_locations":
        # Ensure each part_location has a valid part_id that actually exists in `parts`.
        parts_csv = csv_path.parent / "parts.csv"
        part_ids: list[str] = []
        if parts_csv.exists():
            with parts_csv.open(newline="") as pf:
                reader = csv.DictReader(pf)
                for prow in reader:
                    pid = prow.get("id")
                    if pid:
                        part_ids.append(pid)

        if not part_ids:
            print(
                f"[WARN] No parts.csv or no part IDs found; "
                f"leaving part_locations.part_id as-is for {len(rows)} rows."
            )
        else:
            import itertools

            cycle_ids = itertools.cycle(part_ids)
            for row in rows:
                # If the CSV row doesn't specify part_id, assign one in a round-robin fashion.
                if not row.get("part_id"):
                    row["part_id"] = next(cycle_ids)

    with csv_path.open("w", newline="", encoding="utf8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        if rows:
            writer.writerows(rows)

    if rows:
        print(f"  ✔ wrote {csv_path}")
    else:
        print(f"  ⚠ wrote EMPTY CSV for {table_name} → {csv_path}")

def generate_unit_standard_map(
    tables: Dict[str, Table],
    generated: Dict[str, List[Dict[str, str]]],
    out_dir: Path,
    rows: int,
) -> None:
    """
    Special-case generator for unit_standard_map:
    - Uses already-generated curriculum_units and standards.
    - Produces up to min(len(units), len(standards), rows) distinct pairs.
    - Guarantees no duplicate (unit_id, standard_id).
    """
    table_name = "unit_standard_map"
    table = tables[table_name]

    units = generated.get("curriculum_units") or []
    standards = generated.get("standards") or []

    if not units or not standards:
        print(
            "[warn] unit_standard_map: parents curriculum_units/standards "
            "not generated or empty; writing EMPTY CSV."
        )
        write_csv_for_table(table_name, tables, out_dir, [])
        generated[table_name] = []
        return

    n = min(len(units), len(standards), max(1, rows))

    print(
        f"=== Generating unit_standard_map (special-case join) ===\n"
        f"  using {n} distinct unit/standard pairs "
        f"(units={len(units)}, standards={len(standards)}, rows={rows})"
    )

    rows_out: List[Dict[str, str]] = []

    for i in range(n):
        unit_row = units[i]
        standard_row = standards[i]

        row: Dict[str, str] = {}
        for col in table.columns:
            if col.name == "unit_id":
                row[col.name] = unit_row["id"]
            elif col.name == "standard_id":
                row[col.name] = standard_row["id"]
            else:
                # Fill any extra columns deterministically
                row[col.name] = generate_deterministic_value(table_name, col, i + 1)

        rows_out.append(row)

    write_csv_for_table(table_name, tables, out_dir, rows_out)
    generated[table_name] = rows_out


# ------------------------------------------------------------
# Single-table generation (acyclic or no self-FK)
# ------------------------------------------------------------

def generate_single_table(
    table_name: str,
    tables: Dict[str, Table],
    generated: Dict[str, List[Dict[str, str]]],
    out_dir: Path,
    rows: int,
    raw_dir: Path,
) -> None:
    table = tables[table_name]
    fk_map = get_fk_column_map(table_name, tables)
    n_rows = max(1, rows)
    relax_fk = table_name in RELAX_FK_TABLES

    print(f"\n=== Generating {table_name} (single-table) ===")

    # Skip-data tables: header only
    if table_name in SKIP_DATA_TABLES:
        print(f"  [info] SKIP_DATA_TABLES: writing header-only CSV for {table_name}")
        write_csv_for_table(table_name, tables, out_dir, [])
        generated[table_name] = []
        return

    # SPECIAL CASES for join / constrained tables
    if table_name == "unit_standard_map":
        generate_unit_standard_map(tables, generated, out_dir, rows)
        return

    if table_name == "proposal_standard_map":
        generate_proposal_standard_map(tables, generated, out_dir, rows)
        return

    if table_name == "round_decisions":
        generate_round_decisions(tables, generated, out_dir, rows)
        return

    # Try to load raw_data CSV for this table
    raw_rows = load_raw_rows_for_table(table_name, tables, raw_dir)
    if raw_rows:
        fk_map = get_fk_column_map(table_name, tables)

        # If this table has FKs and we're not relaxing them, rewrite FK columns
        # to point at already-generated parent CSVs, ignoring whatever was in raw_data.
        if fk_map and not relax_fk:
            print(f"  [raw_data] Rewriting FK columns for {table_name}: {fk_map}")
            for i, row in enumerate(raw_rows, start=1):
                for col in table.columns:
                    if col.name not in fk_map:
                        continue

                    parent_table, parent_col = fk_map[col.name]

                    # parent_table should already be generated due to topo order
                    if parent_table not in generated:
                        raise RuntimeError(
                            f"FK ERROR (raw_data): {table_name}.{col.name} depends on "
                            f"{parent_table}.{parent_col}, but parent table "
                            f"has not been generated yet."
                        )

                    parent_rows = generated[parent_table]
                    if not parent_rows:
                        raise RuntimeError(
                            f"FK ERROR (raw_data): {table_name}.{col.name} depends on "
                            f"{parent_table}.{parent_col}, but parent CSV has zero rows."
                        )

                    key = (table_name, col.name)
                    if key in UNIQUE_FK_PER_ROW:
                        parent_idx = (i - 1) % len(parent_rows)
                    else:
                        parent_idx = 0

                    # overwrite whatever was in the raw CSV
                    row[col.name] = parent_rows[parent_idx][parent_col]

        # If relax_fk is True, or there are no FKs, we just trust raw_data as-is.
        write_csv_for_table(table_name, tables, out_dir, raw_rows)
        generated[table_name] = raw_rows
        return

    # No raw_data: synthetic generation
    parents = get_fk_parent_tables(table_name, tables)
    print(f"  FK parents: {parents if parents else '[]'}")
    if relax_fk:
        print(f"  [info] FK enforcement RELAXED for {table_name}")

    rows_out: List[Dict[str, str]] = []

    for i in range(1, n_rows + 1):
        row: Dict[str, str] = {}

        # Fill FK columns first (deterministic, unless relaxed)
        if not relax_fk and fk_map:
            for col in table.columns:
                if col.name in fk_map:
                    parent_table, parent_col = fk_map[col.name]

                    if parent_table == table_name:
                        # Self-FK: point to row 1's parent_col deterministically
                        parent_col_obj = next(
                            (c for c in table.columns if c.name == parent_col),
                            col,
                        )
                        row[col.name] = generate_deterministic_value(
                            table_name, parent_col_obj, 1
                        )
                    else:
                        if parent_table not in generated:
                            raise RuntimeError(
                                f"FK ERROR: {table_name}.{col.name} depends on "
                                f"{parent_table}.{parent_col}, but parent table "
                                f"has not been generated yet."
                            )
                        parent_rows = generated[parent_table]
                        if not parent_rows:
                            raise RuntimeError(
                                f"FK ERROR: {table_name}.{col.name} depends on "
                                f"{parent_table}.{parent_col}, but parent CSV has zero rows."
                            )

                        key = (table_name, col.name)
                        if key in UNIQUE_FK_PER_ROW:
                            parent_idx = (i - 1) % len(parent_rows)
                            row[col.name] = parent_rows[parent_idx][parent_col]
                        else:
                            row[col.name] = parent_rows[0][parent_col]

        # Fill remaining / non-FK columns
        for col in table.columns:
            if col.name not in row:
                row[col.name] = generate_deterministic_value(table_name, col, i)

        # If FK enforcement is relaxed, blank out FK columns to avoid bogus refs
        if relax_fk and fk_map:
            for fk_col in fk_map.keys():
                if fk_col in row:
                    row[fk_col] = ""

        rows_out.append(row)

    write_csv_for_table(table_name, tables, out_dir, rows_out)
    generated[table_name] = rows_out

def generate_round_decisions(
    tables: Dict[str, Table],
    generated: Dict[str, List[Dict[str, str]]],
    out_dir: Path,
    rows: int,
) -> None:
    """
    Generate round_decisions with at most ONE row per review_round_id
    to satisfy the unique index on review_round_id.
    """
    table_name = "round_decisions"
    print(f"\n=== Generating {table_name} (1:1 with review_rounds) ===")

    review_rounds = generated.get("review_rounds", [])
    if not review_rounds:
        print("  [warn] No review_rounds generated; writing EMPTY round_decisions.csv")
        write_csv_for_table(table_name, tables, out_dir, [])
        generated[table_name] = []
        return

    max_rows = min(len(review_rounds), max(1, rows))
    print(f"  [info] Creating {max_rows} decisions for {len(review_rounds)} review_rounds")

    table = tables[table_name]
    rows_out: List[Dict[str, str]] = []

    # Build a quick col lookup
    cols_by_name = {c.name: c for c in table.columns}

    for i in range(1, max_rows + 1):
        rr = review_rounds[i - 1]     # 1:1 by index
        row: Dict[str, str] = {}

        for col in table.columns:
            if col.name == "review_round_id":
                row[col.name] = rr["id"]
            else:
                # Use your deterministic generator so timestamps / text are consistent
                row[col.name] = generate_deterministic_value(table_name, col, i)

        rows_out.append(row)

    write_csv_for_table(table_name, tables, out_dir, rows_out)
    generated[table_name] = rows_out

def generate_proposal_standard_map(
    tables: Dict[str, Table],
    generated: Dict[str, List[Dict[str, str]]],
    out_dir: Path,
    rows: int,
) -> None:
    """
    Generate proposal_standard_map with DISTINCT (proposal_id, standard_id) pairs.

    Strategy:
    - Use already-generated proposals and standards.
    - Pair them up 1:1 (zipped) up to min(len(proposals), len(standards), rows).
    - No duplicates → no PK violations.
    """
    table_name = "proposal_standard_map"
    print(f"\n=== Generating {table_name} (join: proposals ↔ standards) ===")

    proposals = generated.get("proposals", [])
    standards = generated.get("standards", [])

    if not proposals or not standards:
        print(
            f"  [warn] Cannot generate {table_name}: "
            f"proposals={len(proposals)}, standards={len(standards)}"
        )
        write_csv_for_table(table_name, tables, out_dir, [])
        generated[table_name] = []
        return

    max_rows = min(len(proposals), len(standards), max(1, rows))
    print(
        f"  [info] Using {max_rows} distinct pairs out of "
        f"{len(proposals)} proposals × {len(standards)} standards"
    )

    rows_out: List[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for i in range(max_rows):
        proposal = proposals[i]
        standard = standards[i]

        pair = (proposal["id"], standard["id"])
        if pair in seen:
            continue
        seen.add(pair)

        rows_out.append(
            {
                "proposal_id": proposal["id"],
                "standard_id": standard["id"],
            }
        )

    write_csv_for_table(table_name, tables, out_dir, rows_out)
    generated[table_name] = rows_out


def is_int_type(type_str: str) -> bool:
    t = type_str.lower()
    return "int" in t or "serial" in t or "smallint" in t or "bigint" in t


# ------------------------------------------------------------
# SCC group generation (cycles, including self-FKs)
# ------------------------------------------------------------

def generate_scc_group(
    group: List[str],
    tables: Dict[str, Table],
    generated: Dict[str, List[Dict[str, str]]],
    out_dir: Path,
    rows: int,
    raw_dir: Path,
) -> None:
    """
    Generate all tables in an SCC as a batch.

    - If raw_data CSVs are present for tables in this SCC, use those rows
      as the base data (normalized to schema and UUID-safe).
    - Pre-assign deterministic non-FK values (including IDs) where needed.
    - For internal FKs, tie row i in child to row i in parent.
    - For external FKs, use the first row of the already-generated parent table.
    - For RELAX_FK_TABLES or RELAX_FK_COLUMNS, FK columns are left blank ("").
    """
    # First, see if any tables in this group have raw_data
    raw_rows_map: Dict[str, List[Dict[str, str]]] = {}
    for tbl in group:
        if tbl in SKIP_DATA_TABLES:
            write_csv_for_table(tbl, tables, out_dir, [])
            generated[tbl] = []
            continue
        raw_rows = load_raw_rows_for_table(tbl, tables, raw_dir)
        if raw_rows:
            raw_rows_map[tbl] = raw_rows

    # Number of rows for this SCC: respect --rows, but allow raw_data to increase it
    max_raw_rows = max((len(v) for v in raw_rows_map.values()), default=0)
    n_rows = max(1, rows, max_raw_rows)

    print(f"\n=== Generating SCC group: {group} ===")
    for tbl in group:
        parents = get_fk_parent_tables(tbl, tables)
        relax_fk = tbl in RELAX_FK_TABLES
        flags = []
        if relax_fk:
            flags.append("RELAX_FK")
        if tbl in SKIP_DATA_TABLES:
            flags.append("SKIP_DATA")
        if tbl in raw_rows_map:
            flags.append("RAW_DATA")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        print(f"  - {tbl}{flag_str} FK parents: {parents if parents else '[]'}")

    # Step A: pre-assign all non-FK values (base rows, including raw-data if present)
    preassigned: Dict[str, List[Dict[str, str]]] = {}
    for tbl in group:
        table = tables[tbl]
        fk_map = get_fk_column_map(tbl, tables)

        if tbl in SKIP_DATA_TABLES:
            preassigned[tbl] = []
            continue

        base_raw_rows = raw_rows_map.get(tbl)
        rows_out: List[Dict[str, str]] = []

        for i in range(1, n_rows + 1):
            row: Dict[str, str] = {}
            source = base_raw_rows[i - 1] if base_raw_rows and i <= len(base_raw_rows) else {}

            for col in table.columns:
                if col.name in fk_map:
                    # leave FK columns to be filled later (even if present in raw source)
                    raw_val = source.get(col.name)
                    row[col.name] = raw_val if raw_val not in (None, "") else None
                else:
                    raw_val = source.get(col.name)
                    if raw_val not in (None, ""):
                        row[col.name] = str(raw_val)
                    else:
                        row[col.name] = generate_deterministic_value(tbl, col, i)

            rows_out.append(row)

        preassigned[tbl] = rows_out

    # Step B: fill FK columns
    for tbl in group:
        if tbl in SKIP_DATA_TABLES:
            continue

        table = tables[tbl]
        fk_map = get_fk_column_map(tbl, tables)

        if not fk_map:
            continue

        for i in range(n_rows):
            row = preassigned[tbl][i]
            for col in table.columns:
                if col.name not in fk_map:
                    continue
                if is_relaxed_fk_column(tbl, col.name):
                    # relaxed FK columns: leave None, will be blanked later
                    continue

                parent_table, parent_col = fk_map[col.name]

                if parent_table in group:
                    # Internal SCC dependency → align rows by index
                    parent_rows = preassigned[parent_table]
                    if not parent_rows:
                        raise RuntimeError(
                            f"SCC FK ERROR: {tbl}.{col.name} depends on "
                            f"{parent_table}.{parent_col} within SCC, "
                            f"but parent table has no rows (possibly skipped)."
                        )
                    row[col.name] = parent_rows[i][parent_col]
                else:
                    # External parent must already be generated
                    if parent_table not in generated:
                        raise RuntimeError(
                            f"SCC FK ERROR: {tbl}.{col.name} depends on "
                            f"{parent_table}.{parent_col}, but {parent_table} "
                            f"has not been generated yet."
                        )
                    parent_rows = generated[parent_table]
                    if not parent_rows:
                        raise RuntimeError(
                            f"SCC FK ERROR: {tbl}.{col.name} depends on "
                            f"{parent_table}.{parent_col}, but parent CSV "
                            f"has zero rows."
                        )
                    # Always use first parent row for determinism (or UNIQUE_FK_PER_ROW spread)
                    key = (tbl, col.name)
                    if key in UNIQUE_FK_PER_ROW:
                        parent_idx = i % len(parent_rows)  # i is 0-based here
                        row[col.name] = parent_rows[parent_idx][parent_col]
                    else:
                        row[col.name] = parent_rows[0][parent_col]

    # Step C: ensure no None values remain (safety)
    for tbl in group:
        if tbl in SKIP_DATA_TABLES:
            continue

        table = tables[tbl]
        fk_map = get_fk_column_map(tbl, tables)
        relax_fk_table = tbl in RELAX_FK_TABLES

        rows_local = preassigned[tbl]
        if not rows_local:
            continue

        for i in range(len(rows_local)):
            row = rows_local[i]
            for col in table.columns:
                if row[col.name] is None:
                    if col.name in fk_map and is_relaxed_fk_column(tbl, col.name):
                        # Column-level relaxed FK: blank it
                        row[col.name] = ""
                    elif relax_fk_table and col.name in fk_map:
                        # Table-level relaxed FK: blank all FK columns
                        row[col.name] = ""
                    else:
                        row[col.name] = generate_deterministic_value(tbl, col, i + 1)

    # Step D: write CSVs and store in generated
    for tbl in group:
        if tbl in SKIP_DATA_TABLES:
            write_csv_for_table(tbl, tables, out_dir, [])
            generated[tbl] = []
            continue

        rows_local = preassigned.get(tbl, [])
        write_csv_for_table(tbl, tables, out_dir, rows_local)
        generated[tbl] = rows_local


# ------------------------------------------------------------
# CSV Generation (SCC-aware, manual-FK, defensive)
# ------------------------------------------------------------

def generate_csv_files(
    dbml_path: Path,
    out_dir: Path,
    rows: int,
    raw_dir: Path,
) -> None:
    tables = parse_dbml(dbml_path)

    # Build + bind manual FKs
    fks = build_manual_fk_list(tables)
    bind_manual_fks_to_tables(tables, fks)

    # Diagnostic output
    print_tables_without_fk_map(tables)

    out_dir.mkdir(exist_ok=True)

    components, table_to_comp = compute_components_and_order(tables, fks)

    print("\n=== Component Generation Order (SCC-aware, MANUAL FKs) ===")
    for idx, group in enumerate(components, start=1):
        # Compute external deps for logging
        external_parents: Set[str] = set()
        for t in group:
            for fk in tables[t].fks_out:
                if fk.parent_table not in group:
                    external_parents.add(fk.parent_table)
        print(
            f"  Component {idx}: {group} "
            f"(depends on: {sorted(external_parents) if external_parents else '[]'})"
        )

    generated: Dict[str, List[Dict[str, str]]] = {}

    for group in components:
        try:
            if len(group) == 1 and not has_self_fk(group[0], tables):
                # Simple, acyclic single table
                generate_single_table(group[0], tables, generated, out_dir, rows, raw_dir)
            else:
                # SCC group (cycle or self-FK)
                generate_scc_group(group, tables, generated, out_dir, rows, raw_dir)
        except RuntimeError as e:
            # Defensive behavior: don't crash; emit empty CSVs for this group.
            print(
                f"\n[WARN] Failed to generate component {group} due to FK error:\n"
                f"       {e}\n"
                f"       → Writing EMPTY CSVs for tables in this component.\n"
            )
            for tbl in group:
                write_csv_for_table(tbl, tables, out_dir, [])
                generated[tbl] = []

    # Also generate tables that have NO FKs defined in MANUAL_FK_MAP at all,
    # but might not appear in the dependency graph if fks is empty.
    if not fks:
        print("\n[INFO] No manual FKs defined; generating all tables independently.")
        for tbl in sorted(tables.keys()):
            if tbl not in generated:
                generate_single_table(tbl, tables, generated, out_dir, rows, raw_dir)

    # --------------------------------------------------------
    # Post-generation FK patching for troublesome relationships
    # --------------------------------------------------------

    # Ensure work_order_parts.part_id always points at a real parts.id
    patch_fk_all(generated, "work_order_parts", "part_id", "parts", "id")

    # If you want to fix other relationships later, you can add more lines like:
    # patch_fk_all(generated, "some_child_table", "fk_col", "parent_table", "id")

    # Re-write patched tables' CSVs
    for tbl in ("work_order_parts",):
        if tbl in generated:
            write_csv_for_table(tbl, tables, out_dir, generated[tbl])

    print("\nAll CSVs generated (manual-FK + defensive + raw-data-aware + UUID-safe).\n")


# ------------------------------------------------------------
# DOT Graph (optional: you can still see DBML refs, but they are NOT trusted)
# ------------------------------------------------------------

def write_fk_graph_dot(dbml_path: Path, dot_path: Path) -> None:
    """
    For now, show MANUAL_FK_MAP graph (since DBML FKs are not trusted).
    """
    tables = parse_dbml(dbml_path)
    fks = build_manual_fk_list(tables)

    lines = ["digraph fks {", "  rankdir=LR;"]

    for t in sorted(tables.keys()):
        lines.append(f'  "{t}";')

    for fk in fks:
        lines.append(f'  "{fk.parent_table}" -> "{fk.child_table}";')

    lines.append("}")

    dot_path.write_text("\n".join(lines))
    print(f"✔ wrote FK graph (manual FKs): {dot_path}")


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    # schema.dbml lives next to this script in seed_csvs/
    parser.add_argument(
        "--dbml",
        default="schema.dbml",
        help="Path to schema.dbml (relative to seed_csvs directory).",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=5,
        help="Number of rows per table (min 1).",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent

    # DBML is in seed_csvs/
    dbml = (script_dir / args.dbml).resolve()

    # CSV dir is a sibling of seed_csvs/: versions/csv
    out = (script_dir.parent / "csv").resolve()
    out.mkdir(parents=True, exist_ok=True)

    # Raw-data dir is also a sibling of seed_csvs/: versions/raw_data
    raw_dir = (script_dir.parent / "raw_data").resolve()
    print(f"[info] Raw-data directory: {raw_dir} (exists={raw_dir.exists()})")

    n_rows = max(1, args.rows)

    # write fk_graph.dot into the csv directory as well
    write_fk_graph_dot(dbml, out / "fk_graph.dot")
    generate_csv_files(dbml, out, n_rows, raw_dir)


if __name__ == "__main__":
    main()
