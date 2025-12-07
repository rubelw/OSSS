#!/usr/bin/env python3

import json
import re
import uuid
import csv
import numbers
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Callable, Tuple, Set
from pathlib import Path
from decimal import Decimal, InvalidOperation


# ---------------------------------------------------------------------
# Hard-coded paths
# ---------------------------------------------------------------------
DBML_PATH = "../../../../../data_model/schema.dbml"
OUT_JSON_PATH = "./seed_full_school.json"
STATES_CSV_PATH = "../data_csv/205_states.csv"
ORGANIZATIONS_CSV_PATH = "../data_csv/000_organizations.csv"
DATA_CSV_DIR = "../data_csv"

# NEW: import the modular builders
from table_overrides.states import (
    load_states_definitions,
    build_states_rows_from_defns,
)
from table_overrides.organizations import (
    build_organizations_rows_from_csv,
)

# ---------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------

@dataclass
class Column:
    name: str
    db_type: str
    is_pk: bool = False


@dataclass
class Table:
    name: str
    columns: List[Column] = field(default_factory=list)


@dataclass
class ForeignKey:
    parent_table: str
    parent_col: str
    child_table: str
    child_col: str


EXTRA_FKS: List[ForeignKey] = [
    # alignments.curriculum_version_id -> curriculum_versions.id
    ForeignKey(
        parent_table="curriculum_versions",
        parent_col="id",
        child_table="alignments",
        child_col="curriculum_version_id",
    ),
    # proposal_reviews.review_round_id -> review_rounds.id
    ForeignKey(
        parent_table="review_rounds",
        parent_col="id",
        child_table="proposal_reviews",
        child_col="review_round_id",
    ),
    # work_order_* -> work_orders.id
    ForeignKey(
        parent_table="work_orders",
        parent_col="id",
        child_table="work_order_parts",
        child_col="work_order_id",
    ),
    ForeignKey(
        parent_table="work_orders",
        parent_col="id",
        child_table="work_order_tasks",
        child_col="work_order_id",
    ),
    ForeignKey(
        parent_table="work_orders",
        parent_col="id",
        child_table="work_order_time_logs",
        child_col="work_order_id",
    ),
    ForeignKey(
        parent_table="assets",
        parent_col="id",
        child_table="asset_parts",
        child_col="asset_id",
    ),
    ForeignKey(
        parent_table="parts",
        parent_col="id",
        child_table="asset_parts",
        child_col="part_id",
    ),
]


# ---------------------------------------------------------------------
# Regex Patterns
# ---------------------------------------------------------------------

TABLE_HEADER_RE = re.compile(r"Table\s+([A-Za-z_0-9\"']+)\s*\{")
REF_RE = re.compile(
    r"Ref:\s+([A-Za-z_0-9]+)\.([A-Za-z_0-9]+)\s*>\s*([A-Za-z_0-9]+)\.([A-Za-z_0-9]+)"
)
ENUM_HEADER_RE = re.compile(r"Enum\s+([A-Za-z_0-9\"']+)\s*\{")


# ---------------------------------------------------------------------
# Generic CSV loaders (for hundreds of tables)
# ---------------------------------------------------------------------

# pattern: 000_organizations.csv → table "organizations"
#          205_states.csv         → table "states"
#          users.csv              → table "users"
CSV_FILENAME_RE = re.compile(
    r"^(?P<prefix>\d+_)?(?P<table>[A-Za-z0-9_]+)\.csv$"
)

def to_decimal(val, default=0):
    """Best-effort convert to Decimal; fall back to default on junk."""
    try:
        if isinstance(val, (int, float, Decimal)):
            return Decimal(str(val))
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)

def discover_table_csv_files(
    data_dir: str | Path = DATA_CSV_DIR,
) -> Dict[str, Path]:
    """
    Scan DATA_CSV_DIR for CSV files and map them to table names.

    Convention:
      * NNN_table_name.csv  → table_name
      * table_name.csv      → table_name
    """
    root = Path(data_dir)
    mapping: Dict[str, Path] = {}

    if not root.exists():
        return mapping

    for p in root.glob("*.csv"):
        m = CSV_FILENAME_RE.match(p.name)
        if not m:
            continue
        table_name = m.group("table")
        mapping[table_name] = p

    return mapping


def load_generic_csv_rows(csv_path: Path) -> List[Dict[str, str]]:
    """
    Load rows from an arbitrary CSV using DictReader.

    - Strips whitespace off keys and values.
    - Skips completely empty rows.
    """
    rows: List[Dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return rows

        fieldnames = [fn.strip() for fn in reader.fieldnames]  # noqa: F841
        for raw in reader:
            # Normalize keys and values
            row = {}
            empty = True
            for k, v in raw.items():
                if k is None:
                    continue
                key = k.strip()
                val = v.strip() if isinstance(v, str) else v
                if val not in (None, ""):
                    empty = False
                row[key] = val
            if not empty:
                rows.append(row)
    return rows


def coerce_csv_value(raw: Any, col: Column) -> Any:
    """
    Best-effort coercion from CSV string to the column's Python type.
    Keep it simple: ints, bools, and leave the rest as strings.
    """
    if raw is None:
        return None

    s = str(raw).strip()
    if s == "":
        return None

    t = col.db_type.lower()

    # Integer-ish types
    if any(kw in t for kw in ("int", "bigint", "smallint")):
        try:
            return int(s)
        except ValueError:
            return s

    # Boolean-ish
    if "bool" in t:
        if s.lower() in ("true", "t", "1", "yes", "y"):
            return True
        if s.lower() in ("false", "f", "0", "no", "n"):
            return False
        return s

    # Leave everything else as string
    return s


def build_rows_from_csv(
    table: Table,
    csv_rows: List[Dict[str, str]],
    enums: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for idx, raw in enumerate(csv_rows):
        row: Dict[str, Any] = {}

        for col in table.columns:
            col_name = col.name

            if is_tsvector_col(col):
                continue

            raw_val = raw.get(col_name)

            if raw_val not in (None, ""):
                row[col_name] = coerce_csv_value(raw_val, col)
            else:
                if col_name == "id" and is_uuid_col(col):
                    seed = f"{table.name}:{idx}:{json.dumps(raw, sort_keys=True)}"
                    row[col_name] = stable_uuid(seed)
                else:
                    row[col_name] = sample_value(table, col, enums)

        # 🔹 Ensure bus_stop_times always has non-null times
        if table.name == "bus_stop_times":
            if not row.get("arrival_time"):
                row["arrival_time"] = "08:00:00"
            if not row.get("departure_time"):
                row["departure_time"] = "08:10:00"

        rows.append(row)

    return rows


# ---------------------------------------------------------------------
# Per-table override registry
# ---------------------------------------------------------------------

# Signature:
#   loader(table, enums, csv_rows) -> list[dict]
TableLoader = Callable[
    ["Table", Dict[str, List[str]], List[Dict[str, str]]],
    List[Dict[str, Any]],
]

CUSTOM_TABLE_LOADERS: Dict[str, TableLoader] = {}


def register_table_loader(table_name: str) -> Callable[[TableLoader], TableLoader]:
    """
    Decorator to register a custom loader for a specific table.

    Example:

        @register_table_loader("education_associations")
        def load_education_associations(table, enums, csv_rows):
            rows = []
            ...
            return rows
    """
    def decorator(func: TableLoader) -> TableLoader:
        CUSTOM_TABLE_LOADERS[table_name] = func
        return func
    return decorator


# ---------------------------------------------------------------------
# Auto-import all table override modules from table_overrides/
# ---------------------------------------------------------------------
import importlib
import pkgutil
import pathlib
import sys


def load_table_override_modules():
    overrides_dir = pathlib.Path(__file__).parent / "table_overrides"

    if not overrides_dir.exists():
        return

    # Add parent dir to Python path so imports resolve
    sys.path.insert(0, str(overrides_dir.parent))

    package_name = "table_overrides"

    for module_info in pkgutil.iter_modules([str(overrides_dir)]):
        mod_name = f"{package_name}.{module_info.name}"
        importlib.import_module(mod_name)


# Load overrides NOW (they register themselves via decorator)
load_table_override_modules()


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def strip_quotes(name: str) -> str:
    if name.startswith(("'", '"')) and name.endswith(("'", '"')):
        return name[1:-1]
    return name


# ---------------------------------------------------------------------
# Parse DBML: Tables
# ---------------------------------------------------------------------

def parse_tables(dbml_text: str) -> Dict[str, Table]:
    tables: Dict[str, Table] = {}

    for m in TABLE_HEADER_RE.finditer(dbml_text):
        raw_name = m.group(1)
        table_name = strip_quotes(raw_name)

        # Find { ... } block
        start_brace = dbml_text.find("{", m.start())
        depth = 1
        i = start_brace + 1
        while i < len(dbml_text) and depth > 0:
            if dbml_text[i] == "{":
                depth += 1
            elif dbml_text[i] == "}":
                depth -= 1
            i += 1

        block = dbml_text[start_brace + 1: i - 1]

        t = Table(name=table_name)
        parse_table_block(t, block)
        tables[table_name] = t

    return tables


def parse_table_block(table: Table, block: str) -> None:
    in_indexes = False

    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue

        if line.startswith("Indexes"):
            in_indexes = True
            continue
        if in_indexes:
            if line.startswith("}"):
                in_indexes = False
            continue

        if line.startswith("Ref"):
            continue

        # Column syntax: name type [attrs]
        before_attrs = line.split("[", 1)[0].strip()
        if not before_attrs:
            continue

        parts = before_attrs.split()
        if len(parts) < 2:
            continue

        col_name = parts[0]
        col_type = " ".join(parts[1:]).strip()

        attrs = ""
        if "[" in line and "]" in line:
            attrs = line[line.index("[") + 1: line.index("]")]
        is_pk = "pk" in attrs.replace(" ", "").lower()

        table.columns.append(Column(name=col_name, db_type=col_type, is_pk=is_pk))


# ---------------------------------------------------------------------
# Parse DBML: Foreign Keys
# ---------------------------------------------------------------------

def parse_foreign_keys(dbml_text: str) -> List[ForeignKey]:
    fks: List[ForeignKey] = []
    for m in REF_RE.finditer(dbml_text):
        child_table, child_col, parent_table, parent_col = (
            m.group(1),
            m.group(2),
            m.group(3),
            m.group(4),
        )
        fks.append(ForeignKey(
            parent_table=parent_table,
            parent_col=parent_col,
            child_table=child_table,
            child_col=child_col,
        ))
    return fks


# ---------------------------------------------------------------------
# Parse DBML: Enums
# ---------------------------------------------------------------------

def parse_enums(dbml_text: str) -> Dict[str, List[str]]:
    """
    Parse Enum definitions from DBML.

    Returns dict: { "guardianinvitationstate": ["pending", "accepted", "expired"], ... }
    """
    enums: Dict[str, List[str]] = {}

    for m in ENUM_HEADER_RE.finditer(dbml_text):
        raw_name = m.group(1)
        # 🔽 normalize enum name to lowercase
        enum_name = strip_quotes(raw_name).lower()

        # Find { ... } block for Enum
        start_brace = dbml_text.find("{", m.start())
        depth = 1
        i = start_brace + 1
        while i < len(dbml_text) and depth > 0:
            if dbml_text[i] == "{":
                depth += 1
            elif dbml_text[i] == "}":
                depth -= 1
            i += 1

        block = dbml_text[start_brace + 1: i - 1]

        values: List[str] = []
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("//"):
                continue

            # Value is before first space, '[' or '//'
            token = re.split(r"\s|\[|//", line, 1)[0].strip()
            if not token:
                continue
            value = strip_quotes(token)
            values.append(value)

        if values:
            enums[enum_name] = values

    return enums


# ---------------------------------------------------------------------
# Topological Sort
# ---------------------------------------------------------------------

def compute_insert_order(tables: Dict[str, Table], fks: List[ForeignKey]) -> List[str]:
    all_tables = set(tables.keys())

    edges = {t: set() for t in all_tables}
    indegree = {t: 0 for t in all_tables}

    for fk in fks:
        # 🚫 Ignore self-FKs; they just create cycles for seeding
        if fk.parent_table == fk.child_table:
            continue

        if fk.parent_table in all_tables and fk.child_table in all_tables:
            if fk.child_table not in edges[fk.parent_table]:
                edges[fk.parent_table].add(fk.child_table)
                indegree[fk.child_table] += 1

    # Kahn’s algorithm
    queue = sorted([t for t in all_tables if indegree[t] == 0])
    order: List[str] = []

    while queue:
        t = queue.pop(0)
        order.append(t)
        for child in sorted(edges[t]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    leftovers = [t for t in all_tables if t not in order]
    return order + sorted(leftovers)


# ---------------------------------------------------------------------
# Sample Value Generation
# ---------------------------------------------------------------------

def stable_uuid(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def is_uuid_col(col: Column) -> bool:
    n = col.name
    t = col.db_type.lower()
    return (
        "uuid" in t
        or "char(36)" in t
        or n == "id"
        or n.endswith("_id")
    )


def is_tsvector_col(col: Column) -> bool:
    return "tsvector" in col.db_type.lower()


def base_type_name(db_type: str) -> str:
    """
    Strip optional markers, array markers, etc. to get a bare type name
    that will match Enum declarations like `Enum guardianinvitationstate`.
    """
    t = db_type.strip()
    # remove optional markers like "guardianinvitationstate?"
    t = t.rstrip("?")
    # remove array markers like "guardianinvitationstate[]"
    t = t.rstrip("[]")
    # 🔽 normalize to lowercase so it matches parse_enums() keys
    return t.lower()


def sample_value(table: Table, col: Column, enums: Dict[str, List[str]]) -> Any:
    name = col.name
    t = col.db_type.lower()
    base_t = base_type_name(col.db_type)


    # -----------------------------------------------------------------
    # GENERIC NUMERIC HANDLING
    # -----------------------------------------------------------------
    # If the DB type looks numeric, return a simple numeric value instead
    # of random text so we don't get InvalidTextRepresentation errors.
    if any(x in base_t for x in ("int", "numeric", "decimal", "real", "double", "float")):
        # Use small non-zero values that won't violate typical constraints
        if name in ("qty", "quantity", "hours"):
            return 1
        if name in ("unit_cost", "extended_cost", "hourly_rate", "cost", "materials_cost", "labor_cost", "other_cost"):
            return 50
        # generic numeric default
        return 1

    # payroll_runs.posted_entry_id → start NULL so we never point at a ghost.
    if table.name == "payroll_runs" and name == "posted_entry_id":
        return None
    # -----------------------------------------------------------------
    # HARD OVERRIDES FOR KNOWN ENUM COLUMNS
    # -----------------------------------------------------------------

    # guardian_invitations.state :: guardianinvitationstate
    if table.name == "guardian_invitations" and name == "state":
        vals = enums.get(base_t)
        if vals:
            return vals[0]  # e.g., "pending"
        return "PENDING"

    # courses.course_state :: course_state
    if table.name == "courses" and name == "course_state":
        vals = enums.get(base_t)
        if vals:
            for v in vals:
                if v.upper() == "PROVISIONED":
                    return v
            return vals[0]
        return "PROVISIONED"

    # announcements.state :: publicationstate
    if table.name == "announcements" and name == "state":
        vals = enums.get(base_t)
        if vals:
            for v in vals:
                if v.upper() == "PUBLISHED":
                    return v
            return vals[0]
        return "PUBLISHED"

    # coursework.work_type :: work_type
    if table.name == "coursework" and name == "work_type":
        vals = enums.get(base_t)
        if vals:
            for v in vals:
                if v.upper() == "ASSIGNMENT":
                    return v
            return vals[0]
        return "ASSIGNMENT"

    # coursework.state :: some publication enum
    if table.name == "coursework" and name == "state":
        vals = enums.get(base_t)
        if vals:
            for v in vals:
                if v.upper() == "PUBLISHED":
                    return v
            return vals[0]
        return "PUBLISHED"

    # materials.type :: materialtype
    if table.name == "materials" and name == "type":
        vals = enums.get(base_t)
        if vals:
            for v in vals:
                if v.upper() in ("LINK", "URL"):
                    return v
            return vals[0]
        return "LINK"

    # student_submissions.state :: submission_state
    if table.name == "student_submissions" and name == "state":
        vals = enums.get(base_t)
        if vals:
            for v in vals:
                if v.upper() in ("TURNED_IN", "SUBMITTED"):
                    return v
            return vals[0]
        return "TURNED_IN"

    # curriculum_units.status :: curriculum_status
    if table.name == "curriculum_units" and name == "status":
        vals = enums.get("curriculum_status") or enums.get(base_t)
        if vals:
            # prefer a sane default
            for v in vals:
                if v.lower() in ("draft", "adopted", "retired"):
                    return v
            return vals[0]
        return "draft"

    # curricula.status :: curriculum_status
    if table.name == "curricula" and name == "status":
        vals = enums.get("curriculum_status") or enums.get(base_t)
        if vals:
            for v in vals:
                if v.lower() in ("draft", "adopted", "retired"):
                    return v
            return vals[0]
        return "draft"

    if table.name == "curriculum_versions" and name == "status":
        vals = enums.get("curriculum_versions") or enums.get(base_t)
        if vals:
            for v in vals:
                if v.lower() in ("draft", "adopted", "retired"):
                    return v
            return vals[0]
        return "draft"

    # approvals.status :: approval_status
    if table.name == "approvals" and name == "status":
        # Try explicit enum name first, then fall back to the base type
        vals = enums.get("approval_status") or enums.get(base_t)
        if vals:
            # Prefer an "active" status if available
            for v in vals:
                if v.lower() == "active":
                    return v
            # Otherwise, just use the first declared enum value
            return vals[0]
        # Last-resort fallback if enum didn’t parse for some reason
        return "active"

    # review_rounds.status :: review_round_status
    if table.name == "review_rounds" and name == "status":
        # Try explicit enum name first, then fall back to base_t
        vals = enums.get("review_round_status") or enums.get(base_t)
        if vals:
            # Prefer something that sounds like an active/in-review state if present
            preferred = ("open", "closed", "canceled")
            for pref in preferred:
                for v in vals:
                    if v.lower() == pref:
                        return v
            # Otherwise just take the first declared enum value
            return vals[0]
        # Last resort fallback if enum didn’t parse for some reason
        return "open"

    # reviews.status :: review_status (or similar)
    if table.name == "reviews" and name == "status":
        # Try explicit enum name first, then fall back to base_t
        vals = enums.get("review_status") or enums.get(base_t)
        if vals:
            preferred = ("draft", "submitted")
            for pref in preferred:
                for v in vals:
                    if v.lower() == pref:
                        return v
            # Otherwise just take the first declared enum value
            return vals[0]
        # Last resort fallback if enum didn’t parse for some reason
        return "submitted"

    # round_decisions.decision :: round_decision
    if table.name == "round_decisions" and name == "decision":
        # Enum round_decision only accepts: approved, approved_wi.., revisions_r.., rejected
        vals = enums.get("round_decision") or enums.get(base_t)
        if vals:
            # Prefer "approved" if present
            for v in vals:
                if v.lower().startswith("approved"):
                    return v
            return vals[0]
        # Last resort: hard-code a valid value
        return "approved"

    # work_assignments.status :: assignment_status
    if table.name == "work_assignments" and name == "status":
        # assignment_status: pending, confirmed, declined, completed
        vals = enums.get("assignment_status") or enums.get(base_t)
        if vals:
            for pref in ("pending", "confirmed", "declined", "completed"):
                for v in vals:
                    if v.lower() == pref:
                        return v
            return vals[0]
        # fallback if enum didn't parse for some reason
        return "pending"

    # tickets.status :: order_status
    if table.name == "tickets" and name == "status":
        # Mirror orders.status behavior, but keep it simple:
        # we know the valid values are: pending, paid, refunded, canceled
        vals = enums.get("order_status") or enums.get(base_t)
        if vals:
            for pref in ("pending", "paid", "canceled", "refunded"):
                for v in vals:
                    if v.lower() == pref:
                        return v
            return vals[0]
        # even if enums didn't parse, we know "pending" is valid
        return "pending"

    # orders.status :: order_status
    if table.name == "orders" and name == "status":
        # order_status: pending, paid, refunded, canceled
        vals = enums.get("order_status") or enums.get(base_t)
        if vals:
            for pref in ("pending", "paid", "canceled"):
                for v in vals:
                    if v.lower() == pref:
                        return v
            # fallback: first declared enum value
            return vals[0]
        # last-resort fallback if enum map is weird/missing
        return "pending"

    # -----------------------------------------------------------------
    # Special case: any column typed as curriculum_status
    # -----------------------------------------------------------------
    if "curriculum_status" in t or base_t == "curriculum_status":
        vals = enums.get("curriculum_status", [])
        if vals:
            for v in vals:
                if v.lower() in ("draft", "adopted", "retired"):
                    return v
            return vals[0]
        return "draft"

    # Work order parts: force numeric fields to be numeric
    if table.name == "work_order_parts" and name in ("qty", "unit_cost", "extended_cost"):
        return 1

    # -----------------------------------------------------------------
    # Generic enum handling
    # -----------------------------------------------------------------


    if base_t in enums:
        vals = enums[base_t]
        if vals:
            return vals[0]

    # UUID-ish columns
    if is_uuid_col(col):
        return stable_uuid(f"{table.name}:{name}")

    # Real tsvector columns → let DB handle defaults
    if is_tsvector_col(col):
        return None

    # Timestamps
    if "timestamp" in t or name in ("created_at", "updated_at"):
        return "2025-09-05T18:25:42+00:00"

    # Dates
    if "date" in t:
        return "2025-09-05"

    # Booleans
    if "bool" in t:
        return True

    # Numerics
    if any(x in t for x in ("int", "numeric", "decimal", "real", "float", "double")):
        return 1

    # Strings
    if any(x in t for x in ("text", "varchar", "char", "string")):
        return f"Sample {table.name} {name}"

    # Fallback
    return f"Sample {table.name} {name}"


# ---------------------------------------------------------------------
# Tables where created_at is actually TSVECTOR
# ---------------------------------------------------------------------

TSVECTOR_CREATED_AT_TABLES = {
    "requirements",
    "education_associations",
    "meetings",
    "alignments",
    "approvals",
    "curricula",
    "curriculum_versions",
    "proposals",
    "review_requests",
}


# ---------------------------------------------------------------------
# Build Seed Data
# ---------------------------------------------------------------------

def normalize_ids_for_table(table: Table, rows: List[Dict[str, Any]]) -> None:
    """
    Ensure that any UUID-style primary key 'id' columns are generated
    via stable_uuid, ignoring CSV / override-provided values.
    """
    for idx, row in enumerate(rows):
        for col in table.columns:
            if col.name == "id" and is_uuid_col(col):
                # build a seed that ignores whatever 'id' was there before
                seed_payload = {k: v for k, v in row.items() if k != "id"}
                seed = f"{table.name}:{idx}:{json.dumps(seed_payload, sort_keys=True)}"
                row["id"] = stable_uuid(seed)

def patch_fk_all(
    data: Dict[str, List[Dict[str, Any]]],
    child_table: str,
    child_col: str,
    parent_table: str,
    parent_col: str = "id",
) -> None:
    """
    Ensure every row in child_table[child_col] points at an existing parent_table[parent_col].

    If the parent table has no rows, we drop the child rows to avoid FK violations.
    """
    rows = data.get(child_table) or []
    parents = data.get(parent_table) or []

    if not rows:
        return

    # If we have no parents, it's safer to not seed this child table at all
    if not parents:
        data[child_table] = []
        return

    parent_id = parents[0].get(parent_col)
    if parent_id is None:
        data[child_table] = []
        return

    for row in rows:
        row[child_col] = parent_id

def fix_tutor_out_numeric_fields(data):
    """Force tutor_out.score and tutor_out.confidence to valid floats."""
    rows = data.get("tutor_out", [])
    new_rows = []
    for row in rows:
        for col in ("score", "confidence"):
            v = row.get(col)
            # if it's already numeric, keep it
            if isinstance(v, (int, float)):
                continue
            # try to parse numeric-looking strings
            try:
                row[col] = float(v)
            except (TypeError, ValueError):
                # otherwise just give it a dummy float in [0,1)
                # (or whatever makes sense for you)
                row[col] = 0.0
        new_rows.append(row)
    data["tutor_out"] = new_rows

def patch_numeric_columns(data, table, cols, default=0):
    rows = data.get(table, [])
    if not rows:
        return

    for row in rows:
        for col in cols:
            if col not in row:
                continue
            v = row[col]
            # keep ints/floats as-is
            if isinstance(v, numbers.Number):
                continue
            # try to coerce numeric-looking strings
            if isinstance(v, str):
                try:
                    row[col] = int(v)
                    continue
                except ValueError:
                    try:
                        row[col] = float(v)
                        continue
                    except ValueError:
                        pass
            # fallback to default
            row[col] = default

def patch_numeric_fk(data, child_table, child_col, parent_table, parent_col):
    """
    Ensure child[child_col] is one of the parent[parent_col].
    If there are no parents, drop all child rows.
    """
    parents = {row[parent_col] for row in data.get(parent_table, []) if parent_col in row}
    if not parents:
        # no valid parent rows: drop children so we stay FK-clean
        data[child_table] = []
        return

    parent_any = next(iter(parents))

    new_rows = []
    for row in data.get(child_table, []):
        if row.get(child_col) not in parents:
            row[child_col] = parent_any
        new_rows.append(row)
    data[child_table] = new_rows

def patch_self_fk(data, table, fk_col):
    """
    For a self-referencing FK like standards.parent_id -> standards.id.
    If fk_col not in the table's own ids, null it out.
    """
    rows = data.get(table, [])
    ids = {row["id"] for row in rows if "id" in row}

    new_rows = []
    for row in rows:
        pid = row.get(fk_col)
        if pid is not None and pid not in ids:
            # simplest: no parent
            row[fk_col] = None
        new_rows.append(row)

    data[table] = new_rows

def fix_payroll_runs_posted_entry(data: Dict[str, List[Dict[str, Any]]]) -> None:
    """
    Ensure payroll_runs.posted_entry_id either points at a real journal_entries.id
    or is set to NULL so it won't violate the FK.
    """
    rows = data.get("payroll_runs") or []
    if not rows:
        return

    je_ids = {row.get("id") for row in data.get("journal_entries", []) if row.get("id")}
    # If there are no journal_entries at all, just null out posted_entry_id
    if not je_ids:
        for row in rows:
            row["posted_entry_id"] = None
        return

    canonical = next(iter(je_ids))
    for row in rows:
        if row.get("posted_entry_id") not in je_ids:
            row["posted_entry_id"] = canonical
    data["payroll_runs"] = rows


def fix_bus_stop_times_times(data: Dict[str, List[Dict[str, Any]]]) -> None:
    """
    Ensure bus_stop_times.arrival_time / departure_time are never NULL
    (even if CSV or synthetic generation left them blank).
    """
    rows = data.get("bus_stop_times") or []
    if not rows:
        return

    for row in rows:
        # Treat empty string / None as missing
        if not row.get("arrival_time"):
            row["arrival_time"] = "08:00:00"
        if not row.get("departure_time"):
            row["departure_time"] = "08:10:00"

    data["bus_stop_times"] = rows



def fix_bus_stop_times(data: Dict[str, List[Dict[str, Any]]]) -> None:
    """
    Ensure bus_stop_times.arrival_time / departure_time are valid, non-null
    time strings, not 'X-...' or 'Sample ...'.
    """
    rows = data.get("bus_stop_times") or []
    if not rows:
        return

    for row in rows:
        at = row.get("arrival_time")
        dt = row.get("departure_time")

        # Treat missing or sentinel-style strings as invalid
        if not at or (isinstance(at, str) and at.startswith("X-")):
            row["arrival_time"] = "08:00:00"

        if not dt or (isinstance(dt, str) and dt.startswith("X-") or dt == f"Sample bus_stop_times departure_time"):
            row["departure_time"] = "08:10:00"

    data["bus_stop_times"] = rows


def fix_bool_fields(data, table, cols, default=False):
    rows = data.get(table, [])
    for row in rows:
        for c in cols:
            v = row.get(c)
            if isinstance(v, bool):
                continue
            # coerce some common string-y truthy/falsey if you like
            if isinstance(v, str) and v.lower() in ("true", "t", "yes", "y", "1"):
                row[c] = True
            elif isinstance(v, str) and v.lower() in ("false", "f", "no", "n", "0"):
                row[c] = False
            else:
                row[c] = default

    data[table] = rows


def fix_gl_fiscal_fk_cluster(data: Dict[str, List[Dict[str, Any]]]) -> None:
    """
    Option B for GL:
      - Keep the GL demo rows
      - Realign fiscal_period_id / entry_id to *existing* parents so we never get
        FK violations like:
          gl_account_balances.fiscal_period_id -> fiscal_periods.id
          journal_entries.fiscal_period_id     -> fiscal_periods.id
          journal_entry_lines.entry_id         -> journal_entries.id
    """
    fiscal_periods = data.get("fiscal_periods") or []
    if not fiscal_periods:
        # No fiscal periods at all: safest is to drop the GL kids
        data["gl_account_balances"] = []
        data["journal_entries"] = []
        data["journal_entry_lines"] = []
        return

    valid_period_ids = {row.get("id") for row in fiscal_periods if row.get("id")}
    if not valid_period_ids:
        data["gl_account_balances"] = []
        data["journal_entries"] = []
        data["journal_entry_lines"] = []
        return

    canonical_period_id = next(iter(valid_period_ids))

    # 1) Align GL tables' fiscal_period_id
    for tbl in ("gl_account_balances", "journal_entries"):
        rows = data.get(tbl) or []
        if not rows:
            continue
        for row in rows:
            if row.get("fiscal_period_id") not in valid_period_ids:
                row["fiscal_period_id"] = canonical_period_id
        data[tbl] = rows

    # 2) Align journal_entry_lines.entry_id with real journal_entries
    journal_entries = data.get("journal_entries") or []
    entry_ids = {row.get("id") for row in journal_entries if row.get("id")}
    if not entry_ids:
        data["journal_entry_lines"] = []
        return

    canonical_entry_id = next(iter(entry_ids))

    jel_rows = data.get("journal_entry_lines") or []
    new_rows = []
    for row in jel_rows:
        if row.get("entry_id") not in entry_ids:
            row["entry_id"] = canonical_entry_id
        new_rows.append(row)
    data["journal_entry_lines"] = new_rows

import random  # make sure this import is present near the top

# ...

def patch_work_orders_request_id(data: dict) -> None:
    """Ensure work_orders.request_id points at a real maintenance_requests.id.

    If we have no maintenance_requests at all, we null out request_id so the FK
    check passes cleanly.
    """
    work_orders = data.get("work_orders") or []
    maintenance_requests = data.get("maintenance_requests") or []

    if not work_orders:
        return

    if not maintenance_requests:
        # No parents → drop the FK so we don't fail FK checks.
        for row in work_orders:
            row["request_id"] = None
        return

    # Collect valid parent IDs
    mr_ids = [mr["id"] for mr in maintenance_requests if "id" in mr]
    if not mr_ids:
        for row in work_orders:
            row["request_id"] = None
        return

    # For each work_order, if request_id is missing or invalid, assign a real one
    for row in work_orders:
        rid = row.get("request_id")
        if rid not in mr_ids:
            row["request_id"] = random.choice(mr_ids)

def build_seed(
    tables: Dict[str, Table],
    fks: List[ForeignKey],
    order: List[str],
    enums: Dict[str, List[str]],
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Set[str]]]:
    """
    Build seed data for all tables, combining:
      * per-table custom loaders via CUSTOM_TABLE_LOADERS,
      * generic CSV loaders for any table with a matching file,
      * and the original sample_value-based synthetic rows.

    Returns:
      (data, seed_stats) where seed_stats has "csv", "override", "synthetic" sets.
    """
    # Map child_table -> list of (child_col, parent_table, parent_col)
    fk_map: Dict[str, List[Any]] = {}
    for fk in fks:
        fk_map.setdefault(fk.child_table, []).append(
            (fk.child_col, fk.parent_table, fk.parent_col)
        )

    data: Dict[str, List[Dict[str, Any]]] = {}

    # Tables we won't seed at all
    SKIP_TABLES = {
        # keep your existing skip list here
    }

    # FK relationships we do NOT want the patcher to "fix"
    BLOCKED_FKS = {
        ("maintenance_requests", "converted_work_order_id"),
        # keep any others you already had
    }

    # Discover all CSVs once
    csv_files_by_table = discover_table_csv_files()
    csv_rows_by_table: Dict[str, List[Dict[str, str]]] = {
        tname: load_generic_csv_rows(path)
        for tname, path in csv_files_by_table.items()
    }

    # Track origin of rows
    tables_seeded_from_csv: Set[str] = set()       # generic/special CSV (including states)
    tables_seeded_from_override: Set[str] = set()  # per-table custom loaders

    # -----------------------------------------------------------------
    # Initial rows
    # -----------------------------------------------------------------
    for tname in order:
        if tname in SKIP_TABLES:
            data[tname] = []
            continue

        t = tables[tname]
        csv_rows = csv_rows_by_table.get(tname, [])

        rows: List[Dict[str, Any]]

        # 1) Per-table override (e.g. agenda_workflows, addresses, organizations, etc.)
        loader = CUSTOM_TABLE_LOADERS.get(tname)
        if loader is not None:
            rows = loader(t, enums, csv_rows)
            tables_seeded_from_override.add(tname)

        # 2) Generic CSV → seed rows from CSV data
        elif csv_rows:
            rows = build_rows_from_csv(t, csv_rows, enums)
            tables_seeded_from_csv.add(tname)

        # 3) Synthetic fallback (old behavior)
        else:
            row: Dict[str, Any] = {}

            excluded_cols = set()
            if tname in TSVECTOR_CREATED_AT_TABLES:
                excluded_cols.add("created_at")

            for col in t.columns:
                if is_tsvector_col(col):
                    continue
                if col.name in excluded_cols:
                    continue
                row[col.name] = sample_value(t, col, enums)

            # table-specific hacks...
            if tname == "bus_stop_times":
                row["arrival_time"] = "08:00:00"
                row["departure_time"] = "08:10:00"
            if tname == "maintenance_requests":
                row["converted_work_order_id"] = None

            rows = [row]

        # 🔑 Ensure IDs are always generated dynamically, ignoring CSV id values
        normalize_ids_for_table(t, rows)

        data[tname] = rows

    # -----------------------------------------------------------------
    # Patch FK references (except the ones we've explicitly blocked)
    # -----------------------------------------------------------------
    for tname in order:
        # 👉 Do NOT patch tables whose data came from CSV or overrides;
        #    we assume they already have correct FK values.
        if tname in tables_seeded_from_csv or tname in tables_seeded_from_override:
            continue

        if tname not in fk_map:
            continue
        if not data.get(tname):
            continue

        # Existing logic: only patch first row
        row = data[tname][0]
        for child_col, parent_table, parent_col in fk_map[tname]:
            if (tname, child_col) in BLOCKED_FKS:
                continue
            if parent_table not in data or not data[parent_table]:
                continue
            parent_row = data[parent_table][0]
            if parent_col in parent_row:
                row[child_col] = parent_row[parent_col]

    # -----------------------------------------------------------------
    # Any additional manual FK patches you already had belong here
    # -----------------------------------------------------------------

    # -------------------------------
    # work_order_time_logs – fix numeric fields
    # -------------------------------
    # Faker gave us nonsense strings for numeric columns (hours, hourly_rate, cost).
    # Normalize them to sane numeric values so Postgres numeric columns accept them.

    for row in data.get("work_order_time_logs", []):
        # Default hours between 0.5 and 8.0 (or just hard-code if you prefer)
        try:
            # If it's already numeric-ish, keep it; otherwise overwrite
            hours_val = float(row.get("hours", 1.0))
        except (TypeError, ValueError):
            hours_val = 1.0

        try:
            rate_val = float(row.get("hourly_rate", 50.0))
        except (TypeError, ValueError):
            rate_val = 50.0

        # Simple cost model; if existing cost isn’t numeric, recompute
        try:
            cost_val = float(row.get("cost", hours_val * rate_val))
        except (TypeError, ValueError):
            cost_val = hours_val * rate_val

        row["hours"] = hours_val
        row["hourly_rate"] = rate_val
        row["cost"] = cost_val

    # -------------------------------
    # work_order_time_logs – fix user_id FK
    # -------------------------------
    # Make sure all work_order_time_logs.user_id values point to real users.

    users = data.get("users", [])
    valid_user_ids = {u["id"] for u in users}

    if users:
        # Prefer a maintenance/admin-ish user if one exists, otherwise first user
        def pick_fallback_user_id() -> str:
            for u in users:
                email = (u.get("email") or "").lower()
                role = (u.get("role") or "").lower()
                if "maintenance" in email or "maintenance" in role or "admin" in email or "admin" in role:
                    return u["id"]
            return users[0]["id"]

        fallback_user_id = pick_fallback_user_id()

        for row in data.get("work_order_time_logs", []):
            if row.get("user_id") not in valid_user_ids:
                row["user_id"] = fallback_user_id
    else:
        # If there are literally no users, just drop the FK to avoid failures
        for row in data.get("work_order_time_logs", []):
            row["user_id"] = None

    # -------------------------------
    # Organization-scoped tables
    # -------------------------------
    patch_fk_all(data, "evaluation_cycles", "org_id", "organizations")
    patch_fk_all(data, "feature_flags", "org_id", "organizations")
    patch_fk_all(data, "folders", "org_id", "organizations")
    patch_fk_all(data, "governing_bodies", "org_id", "organizations")
    patch_fk_all(data, "plans", "org_id", "organizations")
    patch_fk_all(data, "policies", "org_id", "organizations")
    patch_fk_all(data, "schools", "organization_id", "organizations")
    patch_fk_all(data, "committees", "organization_id", "organizations")
    patch_fk_all(data, "channels", "org_id", "organizations")

    # -------------------------------
    # Sports / activities
    # -------------------------------
    patch_fk_all(data, "teams", "season_id", "seasons")

    # -------------------------------
    # Student-related (sessions)
    # -------------------------------
    patch_fk_all(data, "sessions", "student_id", "students")
    # Student health / services / enrollment / finance
    patch_fk_all(data, "medication_administrations", "student_id", "students")
    patch_fk_all(data, "nurse_visits", "student_id", "students")
    patch_fk_all(data, "section504_plans", "student_id", "students")
    patch_fk_all(data, "special_education_cases", "student_id", "students")
    patch_fk_all(data, "student_program_enrollments", "student_id", "students")
    patch_fk_all(data, "student_school_enrollments", "student_id", "students")
    patch_fk_all(data, "waivers", "student_id", "students")

    # -------------------------------
    # User-scoped / user-related tables
    # -------------------------------
    patch_fk_all(data, "files", "created_by", "users")
    patch_fk_all(data, "notifications", "user_id", "users")
    patch_fk_all(data, "personal_notes", "user_id", "users")
    patch_fk_all(data, "deliveries", "user_id", "users")
    patch_fk_all(data, "evaluation_signoffs", "signer_id", "users")
    patch_fk_all(data, "policy_comments", "user_id", "users")

    # Role / auth / accounts
    patch_fk_all(data, "role_permissions", "permission_id", "permissions")
    patch_fk_all(data, "audit_logs", "actor_id", "user_accounts")
    patch_fk_all(data, "messages", "sender_id", "user_accounts")

    # Posts / evaluations / policies → users
    patch_fk_all(data, "posts", "author_id", "users")
    patch_fk_all(data, "evaluation_assignments", "subject_user_id", "users")
    patch_fk_all(data, "evaluation_assignments", "evaluator_user_id", "users")
    patch_fk_all(data, "policy_versions", "created_by", "users")

    # Courses → Users (owner/teacher)
    patch_fk_all(data, "courses", "user_id", "users")

    # -------------------------------
    # Files / attachments
    # -------------------------------
    patch_fk_all(data, "evaluation_reports", "file_id", "files")
    patch_fk_all(data, "post_attachments", "file_id", "files")
    patch_fk_all(data, "evaluation_files", "file_id", "files")
    patch_fk_all(data, "policy_files", "file_id", "files")
    patch_fk_all(data, "agenda_item_files", "file_id", "files")
    patch_fk_all(data, "meeting_files", "file_id", "files")

    # -------------------------------
    # Finance / accounting
    # -------------------------------
    patch_fk_all(data, "journal_entry_lines", "entry_id", "journal_entries")
    patch_fk_all(data, "payroll_runs", "pay_period_id", "pay_periods")

    patch_fk_all(data, "gl_account_balances", "account_id", "gl_accounts")
    patch_fk_all(data, "gl_account_balances", "fiscal_period_id", "fiscal_periods")
    patch_fk_all(data, "journal_entries", "fiscal_period_id", "fiscal_periods")

    patch_fk_all(data, "gl_account_segments", "segment_id", "gl_segments")
    patch_fk_all(data, "gl_account_segments", "value_id", "gl_segment_values")
    patch_fk_all(data, "gl_segment_values", "segment_id", "gl_segments")

    # HR / staffing – tie employees to GL department segment
    patch_fk_all(data, "hr_employees", "department_segment_id", "gl_segments")
    patch_fk_all(data, "hr_positions", "department_segment_id", "gl_segments")

    patch_fk_all(data, "gl_segments", "org_id", "organizations")

    # --- Payroll / HR demo relationships ---
    patch_fk_all(data, "payroll_runs", "posted_entry_id", "journal_entries")
    patch_fk_all(data, "payroll_runs", "created_by_user_id", "users")

    patch_fk_all(data, "employee_deductions", "employee_id", "hr_employees")
    patch_fk_all(data, "employee_deductions", "deduction_code_id", "deduction_codes")

    patch_fk_all(data, "employee_earnings", "employee_id", "hr_employees")
    patch_fk_all(data, "employee_earnings", "earning_code_id", "earning_codes")

    patch_fk_all(data, "paychecks", "employee_id", "hr_employees")

    # --- Messaging ---
    patch_fk_all(data, "message_recipients", "message_id", "messages")
    patch_fk_all(data, "message_recipients", "person_id", "persons")

    # --- SIS guardians / family portal ---
    patch_fk_all(data, "family_portal_access", "student_id", "students")
    patch_fk_all(data, "student_guardians", "student_id", "students")

    # --- Strategic initiatives / owners ---
    patch_fk_all(data, "initiatives", "owner_id", "users")

    # --- Policy workflow ---
    patch_fk_all(data, "policy_approvals", "step_id", "policy_workflow_steps")
    patch_fk_all(data, "policy_approvals", "approver_id", "users")

    # --- Orders / ecommerce ---
    patch_fk_all(data, "orders", "purchaser_user_id", "users")

    # --- Student transportation ---
    patch_fk_all(data, "student_transportation_assignments", "student_id", "students")

    # --- Event staffing ---
    patch_fk_all(data, "work_assignments", "worker_id", "workers")

    # -------------------------------
    # Evaluations
    # -------------------------------
    patch_fk_all(data, "evaluation_responses", "question_id", "evaluation_questions")

    # -------------------------------
    # Work orders cluster
    # -------------------------------
    patch_fk_all(data, "work_orders", "school_id", "schools")
    patch_fk_all(data, "work_orders", "building_id", "buildings")
    patch_fk_all(data, "work_orders", "space_id", "spaces")
    patch_fk_all(data, "work_orders", "asset_id", "assets")
    patch_fk_all(data, "work_orders", "request_id", "maintenance_requests")
    patch_fk_all(data, "work_orders", "assigned_to_user_id", "users")

    patch_fk_all(data, "work_order_tasks", "work_order_id", "work_orders")
    patch_fk_all(data, "work_order_time_logs", "work_order_id", "work_orders")
    patch_fk_all(data, "work_order_parts", "work_order_id", "work_orders")

    # -------------------------------
    # Assets / parts
    # -------------------------------
    # Make sure assets themselves have valid parents
    patch_fk_all(data, "assets", "building_id", "buildings")
    patch_fk_all(data, "assets", "space_id", "spaces")
    patch_self_fk(data, "assets", "parent_asset_id")

    # Children that reference assets
    patch_fk_all(data, "asset_parts", "asset_id", "assets")
    patch_fk_all(data, "asset_parts", "part_id", "parts")

    patch_fk_all(data, "compliance_records", "asset_id", "assets")
    patch_fk_all(data, "meters", "asset_id", "assets")
    patch_fk_all(data, "pm_plans", "asset_id", "assets")
    patch_fk_all(data, "warranties", "asset_id", "assets")
    patch_fk_all(data, "warranties", "vendor_id", "vendors")

    # ==========================
    # Payroll / journal entries
    # ==========================
    patch_fk_all(data, "payroll_runs", "posted_entry_id", "journal_entries")
    patch_fk_all(data, "payroll_runs", "created_by_user_id", "users")

    # ==========================
    # Academic / student-linked
    # ==========================
    patch_fk_all(data, "class_ranks", "student_id", "students")
    patch_fk_all(data, "gpa_calculations", "student_id", "students")
    patch_fk_all(data, "test_results", "student_id", "students")
    patch_fk_all(data, "test_results", "administration_id", "test_administrations")

    # ==========================
    # Governance / committees
    # ==========================
    patch_fk_all(data, "meetings", "committee_id", "committees")
    patch_fk_all(data, "memberships", "committee_id", "committees")

    # ==========================
    # Person-centric tables
    # ==========================
    patch_fk_all(data, "memberships", "person_id", "persons")
    patch_fk_all(data, "incident_participants", "person_id", "persons")
    patch_fk_all(data, "library_checkouts", "person_id", "persons")
    patch_fk_all(data, "library_holds", "person_id", "persons")

    # ==========================
    # HR / positions
    # ==========================
    patch_fk_all(data, "hr_position_assignments", "employee_id", "hr_employees")

    # ==========================
    # Projects / tasks
    # ==========================
    patch_fk_all(data, "project_tasks", "assignee_user_id", "users")

    # ==========================
    # AR / payments
    # ==========================
    patch_fk_all(data, "payments", "invoice_id", "invoices")

    # ==========================
    # Tutoring / Turn In
    # ==========================
    patch_fk_all(data, "turn_in", "session_id", "sessions")

    # -------------------------------
    # Meetings cluster
    # -------------------------------
    patch_fk_all(data, "meeting_publications", "meeting_id", "meetings")
    patch_fk_all(data, "meeting_search_index", "meeting_id", "meetings")
    patch_fk_all(data, "minutes", "meeting_id", "meetings")
    patch_fk_all(data, "publications", "meeting_id", "meetings")
    patch_fk_all(data, "resolutions", "meeting_id", "meetings")

    # Attendance / permissions / authors → users
    patch_fk_all(data, "attendance", "user_id", "users")
    patch_fk_all(data, "meeting_permissions", "user_id", "users")
    patch_fk_all(data, "minutes", "author_id", "users")

    # Governance / meetings
    patch_fk_all(data, "meetings", "org_id", "organizations")
    patch_fk_all(data, "memberships", "committee_id", "committees")

    # -------------------------------
    # Behavior / discipline cluster
    # -------------------------------
    patch_fk_all(data, "consequences", "participant_id", "incident_participants")
    patch_fk_all(data, "consequences", "incident_id", "incidents")

    # -------------------------------
    # Student supports (ELL / health / behavior / finance)
    # -------------------------------
    patch_fk_all(data, "attendance_daily_summary", "student_id", "students")
    patch_fk_all(data, "behavior_interventions", "student_id", "students")
    patch_fk_all(data, "ell_plans", "student_id", "students")
    patch_fk_all(data, "health_profiles", "student_id", "students")
    patch_fk_all(data, "immunization_records", "student_id", "students")
    patch_fk_all(data, "immunization_records", "immunization_id", "immunizations")
    patch_fk_all(data, "invoices", "student_id", "students")
    patch_fk_all(data, "meal_accounts", "student_id", "students")
    patch_fk_all(data, "meal_eligibility_statuses", "student_id", "students")

    # Payroll runs creator user
    patch_fk_all(data, "payroll_runs", "created_by_user_id", "users")

    # -------------------------------
    # Accommodations / IEP
    # -------------------------------
    patch_fk_all(data, "accommodations", "iep_plan_id", "iep_plans")

    # -------------------------------
    # Ticketing / orders
    # -------------------------------
    patch_fk_all(data, "order_line_items", "order_id", "orders")
    patch_fk_all(data, "order_line_items", "ticket_type_id", "ticket_types")

    patch_fk_all(data, "tickets", "order_id", "orders")
    patch_fk_all(data, "scan_results", "ticket_id", "tickets")
    patch_fk_all(data, "ticket_scans", "ticket_id", "tickets")
    patch_fk_all(data, "ticket_scans", "scanned_by_user_id", "users")

    # -------------------------------
    # Standards: framework_id + parent_id
    # -------------------------------
    patch_fk_all(data, "standards", "framework_id", "frameworks")
    patch_self_fk(data, "standards", "parent_id")

    # -------------------------------
    # Person-scoped tables
    # -------------------------------
    fix_bool_fields(data, "person_addresses", ["is_primary"], default=True)
    fix_bool_fields(data, "person_contacts", ["is_primary", "is_emergency"], default=False)

    patch_fk_all(data, "consents", "person_id", "persons")
    patch_fk_all(data, "emergency_contacts", "person_id", "persons")
    patch_fk_all(data, "library_fines", "person_id", "persons")

    patch_fk_all(data, "person_addresses", "person_id", "persons")
    patch_fk_all(data, "person_addresses", "address_id", "addresses")

    patch_fk_all(data, "person_contacts", "person_id", "persons")
    patch_fk_all(data, "person_contacts", "contact_id", "contacts")

    patch_fk_all(data, "students", "person_id", "persons")
    patch_fk_all(data, "user_accounts", "person_id", "persons")
    patch_fk_all(data, "hr_employees", "person_id", "persons")

    # -------------------------------
    # Agenda items / workflows
    # -------------------------------
    patch_fk_all(data, "agenda_item_approvals", "step_id", "agenda_workflow_steps")
    patch_fk_all(data, "agenda_item_approvals", "item_id", "agenda_items")
    patch_fk_all(data, "agenda_item_approvals", "approver_id", "users")

    patch_fk_all(data, "agenda_item_files", "agenda_item_id", "agenda_items")

    patch_fk_all(data, "motions", "agenda_item_id", "agenda_items")
    patch_fk_all(data, "motions", "moved_by_id", "users")
    patch_fk_all(data, "motions", "seconded_by_id", "users")

    patch_fk_all(data, "votes", "motion_id", "motions")
    patch_fk_all(data, "votes", "voter_id", "users")

    # -------------------------------
    # Courses / sections / transcripts
    # -------------------------------
    patch_fk_all(data, "course_prerequisites", "course_id", "courses")
    patch_fk_all(data, "course_prerequisites", "prereq_course_id", "courses")

    patch_fk_all(data, "course_sections", "course_id", "courses")
    patch_fk_all(data, "course_sections", "term_id", "academic_terms")

    patch_fk_all(data, "transcript_lines", "course_id", "courses")

    patch_fk_all(data, "assignment_categories", "section_id", "course_sections")
    patch_fk_all(data, "final_grades", "section_id", "course_sections")

    # Section-based tables should all point at an existing course_section
    patch_fk_all(data, "assignment_categories", "section_id", "course_sections")
    patch_fk_all(data, "final_grades", "section_id", "course_sections")
    patch_fk_all(data, "section_meetings", "section_id", "course_sections")
    patch_fk_all(data, "section_meetings", "period_id", "periods")
    patch_fk_all(data, "section_room_assignments", "section_id", "course_sections")
    patch_fk_all(data, "teacher_section_assignments", "section_id", "course_sections")
    patch_fk_all(data, "student_section_enrollments", "section_id", "course_sections")

    # student_section_enrollments must reference real students too
    patch_fk_all(data, "student_section_enrollments", "student_id", "students")

    patch_fk_all(data, "transcript_lines", "student_id", "students")
    patch_fk_all(data, "transcript_lines", "term_id", "academic_terms")
    patch_fk_all(data, "final_grades", "student_id", "students")
    patch_fk_all(data, "final_grades", "grading_period_id", "grading_periods")

    # Grading / GPA / ranks / report cards
    patch_fk_all(data, "class_ranks", "term_id", "academic_terms")

    patch_fk_all(data, "gpa_calculations", "student_id", "students")
    patch_fk_all(data, "gpa_calculations", "term_id", "academic_terms")

    patch_fk_all(data, "grading_periods", "term_id", "academic_terms")

    # Gradebook / assignments
    patch_fk_all(data, "gradebook_entries", "student_id", "students")
    patch_fk_all(data, "gradebook_entries", "assignment_id", "assignments")


    patch_fk_all(data, "report_cards", "student_id", "students")
    patch_fk_all(data, "report_cards", "term_id", "academic_terms")

    # -------------------------------
    # Tutor topics
    # -------------------------------
    patch_fk_all(data, "topics", "user_id", "users")
    patch_fk_all(data, "topics", "course_id", "courses")

    # -------------------------------
    # Facilities / spaces
    # -------------------------------
    patch_fk_all(data, "spaces", "floor_id", "floors")
    patch_fk_all(data, "spaces", "building_id", "buildings")

    # -------------------------------
    # Maintenance requests / work orders
    # -------------------------------
    patch_fk_all(data, "maintenance_requests", "space_id", "spaces")
    patch_fk_all(data, "maintenance_requests", "building_id", "buildings")
    patch_fk_all(data, "maintenance_requests", "school_id", "schools")
    patch_fk_all(data, "maintenance_requests", "asset_id", "assets")
    patch_fk_all(data, "maintenance_requests", "submitted_by_user_id", "users")

    # Make sure converted_work_order_id only points at real work_orders
    #patch_fk_all(data, "maintenance_requests", "converted_work_order_id", "work_orders")

    # -------------------------------
    # Maintenance requests / work orders – break cyclic FKs in seed
    # -------------------------------
    # We don't want seed data to enforce the two-way relationship
    # between maintenance_requests and work_orders, because the
    # random UUIDs and load order cause FK problems.

    # 1) Nuke maintenance_requests.converted_work_order_id
    for row in data.get("maintenance_requests", []):
        # Regardless of what's in the source, don't link to work_orders
        row["converted_work_order_id"] = None

    # 2) Nuke work_orders.request_id
    for row in data.get("work_orders", []):
        # Avoid FK to maintenance_requests and the uq_work_orders_request_id constraint
        row["request_id"] = None


    # Extra safety: if anything slipped through, null out bad converted_work_order_id values
    valid_work_order_ids = {row["id"] for row in data.get("work_orders", [])}
    for row in data.get("maintenance_requests", []):
        cid = row.get("converted_work_order_id")
        if cid and cid not in valid_work_order_ids:
            row["converted_work_order_id"] = None

    # -------------------------------
    # Curriculum versions / standards / reviews
    # -------------------------------
    patch_fk_all(data, "alignments", "curriculum_version_id", "curriculum_versions")
    patch_fk_all(data, "alignments", "requirement_id", "requirements")

    patch_fk_all(data, "review_requests", "curriculum_version_id", "curriculum_versions")
    patch_fk_all(data, "review_requests", "association_id", "education_associations")

    patch_fk_all(data, "unit_standard_map", "unit_id", "curriculum_units")
    patch_fk_all(data, "unit_standard_map", "standard_id", "standards")

    patch_fk_all(data, "proposal_standard_map", "proposal_id", "proposals")
    patch_fk_all(data, "proposal_standard_map", "standard_id", "standards")

    patch_fk_all(data, "proposals", "course_id", "courses")
    patch_fk_all(data, "proposals", "curriculum_id", "curricula")
    patch_fk_all(data, "proposals", "organization_id", "organizations")
    patch_fk_all(data, "proposals", "association_id", "education_associations")
    patch_fk_all(data, "proposals", "committee_id", "committees")
    patch_fk_all(data, "proposals", "submitted_by_id", "users")
    patch_fk_all(data, "proposals", "school_id", "schools")
    patch_fk_all(data, "proposals", "subject_id", "subjects")

    patch_fk_all(data, "proposal_reviews", "proposal_id", "proposals")
    patch_fk_all(data, "proposal_reviews", "review_round_id", "review_rounds")
    # 🔹 Reviewer is a PERSON here
    patch_fk_all(data, "proposal_reviews", "reviewer_id", "persons")

    patch_fk_all(data, "reviews", "review_round_id", "review_rounds")
    patch_fk_all(data, "reviews", "reviewer_id", "reviewers")

    patch_fk_all(data, "round_decisions", "review_round_id", "review_rounds")

    # Curricula itself must point at real orgs / proposals
    patch_fk_all(data, "curricula", "organization_id", "organizations")
    patch_fk_all(data, "curricula", "proposal_id", "proposals")


    # -------------------------------
    # Documents / activity / versions
    # -------------------------------
    patch_fk_all(data, "document_activity", "actor_id", "users")
    patch_fk_all(data, "document_activity", "document_id", "documents")

    patch_fk_all(data, "document_notifications", "user_id", "users")
    patch_fk_all(data, "document_notifications", "document_id", "documents")

    patch_fk_all(data, "document_versions", "document_id", "documents")
    patch_fk_all(data, "document_versions", "file_id", "files")
    patch_fk_all(data, "document_versions", "created_by", "users")

    # -------------------------------
    # Space / asset usage & logistics
    # -------------------------------
    patch_fk_all(data, "move_orders", "project_id", "projects")
    patch_fk_all(data, "move_orders", "person_id", "users")
    patch_fk_all(data, "move_orders", "from_space_id", "spaces")
    patch_fk_all(data, "move_orders", "to_space_id", "spaces")

    patch_fk_all(data, "part_locations", "part_id", "parts")
    patch_fk_all(data, "part_locations", "building_id", "buildings")
    patch_fk_all(data, "part_locations", "space_id", "spaces")

    patch_fk_all(data, "space_reservations", "space_id", "spaces")
    patch_fk_all(data, "space_reservations", "booked_by_user_id", "users")

    # -------------------------------
    # Coursework / assignments / attendance_events
    # -------------------------------
    patch_fk_all(data, "assignments", "section_id", "course_sections")
    patch_fk_all(data, "assignments", "category_id", "assignment_categories")

    patch_fk_all(data, "attendance_events", "student_id", "students")
    patch_fk_all(data, "attendance_events", "section_meeting_id", "section_meetings")
    patch_fk_all(data, "attendance_events", "code", "attendance_codes")

    # -------------------------------
    # Student submissions: enum mismatch
    # -------------------------------
    # The DB enum submission_state does not accept our generated values
    # (e.g. "submitted"), and we can't see the allowed labels here.
    # For now, drop all demo rows so seeding doesn't fail.
    if "student_submissions" in data:
        data["student_submissions"] = []

    # -------------------------------
    # Fiscal years / periods (numeric)
    # -------------------------------
    patch_numeric_fk(
        data,
        child_table="fiscal_periods",
        child_col="year_number",
        parent_table="fiscal_years",
        parent_col="year_number",
    )

    # Normalize numeric cost fields in work_orders
    patch_numeric_columns(
        data,
        "work_orders",
        ["materials_cost", "labor_cost", "other_cost"],
        default=0,
    )

    # 1) Make sure work_orders.request_id points at existing maintenance_requests.id,
    #    without violating the unique constraint uq_work_orders_request_id.
    maintenance_requests = data.get("maintenance_requests", [])
    work_orders = data.get("work_orders", [])

    if maintenance_requests and work_orders:
        # All valid maintenance request IDs
        valid_mr_ids = [
            row["id"] for row in maintenance_requests
            if row.get("id")
        ]
        valid_mr_ids_set = set(valid_mr_ids)
        print(f"[seed] maintenance_requests ids: {valid_mr_ids_set}")

        used_mr_ids = set()
        needing_request: list[dict] = []

        # Pass 1: keep at most one work_order per maintenance_request;
        # clear invalid or duplicate request_ids.
        for wo in work_orders:
            rid = wo.get("request_id")
            if rid in valid_mr_ids_set and rid not in used_mr_ids:
                # First time we've seen this MR id: keep it
                used_mr_ids.add(rid)
            else:
                # Either invalid or duplicate -> clear and mark for reassignment
                if "request_id" in wo:
                    wo["request_id"] = None
                needing_request.append(wo)

        # Pass 2: assign any still-unused maintenance_requests.id values to
        # work_orders that need one, at most one per work_order.
        available_mr_ids = [
            mr_id for mr_id in valid_mr_ids
            if mr_id not in used_mr_ids
        ]

        for wo, mr_id in zip(needing_request, available_mr_ids):
            wo["request_id"] = mr_id

        # Any remaining work_orders in needing_request will keep request_id=NULL,
        # which is valid under uq_work_orders_request_id.

    # 🔎 Option B: realign GL demo rows to valid fiscal periods / entries
    fix_gl_fiscal_fk_cluster(data)


    # Final cleanup / safety passes
    fix_bus_stop_times_times(data)
    fix_tutor_out_numeric_fields(data)

    # -----------------------------------------------------------------
    # Final safety scrub: ensure no created_at leaked into tsvector tables
    # -----------------------------------------------------------------
    for tname in TSVECTOR_CREATED_AT_TABLES:
        if tname in data:
            for row in data[tname]:
                row.pop("created_at", None)


    # -----------------------------------------------------------------
    # Final hard overrides for known troublemakers
    # -----------------------------------------------------------------

    # 1) payroll_runs.posted_entry_id → always FK-safe
    pr_rows = data.get("payroll_runs") or []
    if pr_rows:
        journal_entries = data.get("journal_entries") or []
        # If we have at least one journal_entry, point at it.
        # Otherwise leave posted_entry_id as NULL to satisfy the FK.
        je_id = journal_entries[0].get("id") if journal_entries else None
        for row in pr_rows:
            row["posted_entry_id"] = je_id
        data["payroll_runs"] = pr_rows

    # -------------------------------
    # work_order_parts – fix numeric fields
    # -------------------------------

    wop_rows = data.get("work_order_parts", [])

    for row in wop_rows:
        # qty: at least 1, integer
        qty_dec = to_decimal(row.get("qty"), default=1)
        if qty_dec <= 0:
            qty_dec = Decimal(1)
        row["qty"] = int(qty_dec)

        # unit_cost: default to something reasonable like $25
        unit_cost_dec = to_decimal(row.get("unit_cost"), default=25)
        if unit_cost_dec < 0:
            unit_cost_dec = abs(unit_cost_dec)
        row["unit_cost"] = float(unit_cost_dec)

        # extended_cost: if invalid or <=0, compute qty * unit_cost
        ext_dec = to_decimal(row.get("extended_cost"), default=0)
        if ext_dec <= 0:
            ext_dec = qty_dec * unit_cost_dec
        row["extended_cost"] = float(ext_dec)

    # -----------------------------------------------------------------
    # Build seed_stats for reporting
    # -----------------------------------------------------------------
    all_table_names: Set[str] = set(tables.keys())
    synthetic_tables: Set[str] = (
        all_table_names - tables_seeded_from_csv - tables_seeded_from_override
    )

    seed_stats: Dict[str, Set[str]] = {
        "csv": tables_seeded_from_csv,
        "override": tables_seeded_from_override,
        "synthetic": synthetic_tables,
    }

    # 🔧 Fix any weird/sentinel values in bus_stop_times
    fix_bus_stop_times(data)

    fix_tutor_out_numeric_fields(data)


    return data, seed_stats



def ensure_parent_before_child(order: List[str], parent: str, child: str) -> None:
    """
    If `child` appears before `parent` in the list, move `child`
    to immediately after `parent`. Operates in-place.
    """
    if parent not in order or child not in order:
        return
    pi = order.index(parent)
    ci = order.index(child)
    if ci < pi:
        # remove child from its old spot
        order.pop(ci)
        # parent index may have shifted if ci < pi
        pi = order.index(parent)
        order.insert(pi + 1, child)


# ---------------------------------------------------------------------
# Main Entry
# ---------------------------------------------------------------------

def main():
    with open(DBML_PATH, "r", encoding="utf-8") as f:
        dbml_text = f.read()

    tables = parse_tables(dbml_text)
    fks = parse_foreign_keys(dbml_text)
    enums = parse_enums(dbml_text)

    # Add known FKs that DBML doesn't express clearly
    fks.extend(EXTRA_FKS)

    order = compute_insert_order(tables, fks)
    data, seed_stats = build_seed(tables, fks, order, enums)

    # --- manual fixes for cyclic clusters ---
    ensure_parent_before_child(order, "assets", "asset_parts")
    ensure_parent_before_child(order, "review_rounds", "proposal_reviews")
    ensure_parent_before_child(order, "curriculum_versions", "alignments")

    # ✅ work_orders before its children
    ensure_parent_before_child(order, "work_orders", "work_order_parts")
    ensure_parent_before_child(order, "work_orders", "work_order_tasks")
    ensure_parent_before_child(order, "work_orders", "work_order_time_logs")

    # ✅ GL / finance cluster
    ensure_parent_before_child(order, "fiscal_periods", "gl_account_balances")
    ensure_parent_before_child(order, "fiscal_periods", "journal_entries")
    ensure_parent_before_child(order, "journal_entries", "journal_entry_lines")

    # Payroll / journal cluster
    ensure_parent_before_child(order, "journal_entries", "payroll_runs")

    # Students before student-linked tables
    ensure_parent_before_child(order, "students", "class_ranks")
    ensure_parent_before_child(order, "students", "gpa_calculations")
    ensure_parent_before_child(order, "students", "test_results")
    ensure_parent_before_child(order, "test_administrations", "test_results")

    # Governance / committees & memberships
    ensure_parent_before_child(order, "committees", "meetings")
    ensure_parent_before_child(order, "committees", "memberships")

    # Persons before all the person-based tables
    ensure_parent_before_child(order, "persons", "memberships")
    ensure_parent_before_child(order, "persons", "incident_participants")
    ensure_parent_before_child(order, "persons", "library_checkouts")
    ensure_parent_before_child(order, "persons", "library_holds")

    # HR cluster
    ensure_parent_before_child(order, "hr_employees", "hr_position_assignments")

    # Projects & tasks
    ensure_parent_before_child(order, "projects", "project_tasks")
    ensure_parent_before_child(order, "users", "project_tasks")

    # Invoices / payments
    ensure_parent_before_child(order, "invoices", "payments")

    # Sessions / Turn In
    ensure_parent_before_child(order, "sessions", "turn_in")

    # ✅ GL segments / HR
    ensure_parent_before_child(order, "gl_segments", "hr_employees")

    # ✅ Students before all student-support tables
    ensure_parent_before_child(order, "students", "medication_administrations")
    ensure_parent_before_child(order, "students", "nurse_visits")
    ensure_parent_before_child(order, "students", "section504_plans")
    ensure_parent_before_child(order, "students", "special_education_cases")
    ensure_parent_before_child(order, "students", "student_program_enrollments")
    ensure_parent_before_child(order, "students", "student_school_enrollments")
    ensure_parent_before_child(order, "students", "waivers")

    # ✅ Academic terms before term-based tables
    ensure_parent_before_child(order, "academic_terms", "class_ranks")
    ensure_parent_before_child(order, "academic_terms", "gpa_calculations")
    ensure_parent_before_child(order, "academic_terms", "grading_periods")

    # ✅ Users before payroll_runs
    ensure_parent_before_child(order, "users", "payroll_runs")

    payload = {"insert_order": order, "data": data}

    with open(OUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"✔️ Seed file generated:\n{OUT_JSON_PATH}")
    print(f"✔️ Tables: {len(order)}")
    print(f"✔️ Enums detected: {sorted(enums.keys())}")

    # Seeding summary: CSV vs overrides vs synthetic
    csv_tables = sorted(seed_stats["csv"])
    override_tables = sorted(seed_stats["override"])
    synthetic_tables = sorted(seed_stats["synthetic"])

    print("✔️ Seeding summary:")
    print(
        f"  CSV tables ({len(csv_tables)}): "
        f"{', '.join(csv_tables) if csv_tables else '-'}"
    )
    print(
        f"  Override tables ({len(override_tables)}): "
        f"{', '.join(override_tables) if override_tables else '-'}"
    )
    print(
        f"  Synthetic tables ({len(synthetic_tables)}): "
        f"{', '.join(synthetic_tables) if synthetic_tables else '-'}"
    )


if __name__ == "__main__":
    main()
