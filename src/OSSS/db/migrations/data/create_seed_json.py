#!/usr/bin/env python3

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List


# ---------------------------------------------------------------------
# Hard-coded paths
# ---------------------------------------------------------------------
DBML_PATH = "../../../../../data_model/schema.dbml"
OUT_JSON_PATH = "./seed_full_school.json"


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

        block = dbml_text[start_brace + 1 : i - 1]

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
            attrs = line[line.index("[") + 1 : line.index("]")]
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
        enum_name = strip_quotes(raw_name)

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

        block = dbml_text[start_brace + 1 : i - 1]

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

    # Append any remaining (cycles)
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
    return t


def sample_value(table: Table, col: Column, enums: Dict[str, List[str]]) -> Any:
    name = col.name
    t = col.db_type.lower()
    base_t = base_type_name(col.db_type)

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

def build_seed(
    tables: Dict[str, Table],
    fks: List[ForeignKey],
    order: List[str],
    enums: Dict[str, List[str]],
) -> Dict[str, List[Dict[str, Any]]]:
    fk_map: Dict[str, List[Any]] = {}
    for fk in fks:
        fk_map.setdefault(fk.child_table, []).append(
            (fk.child_col, fk.parent_table, fk.parent_col)
        )

    data: Dict[str, List[Dict[str, Any]]] = {}

    # Tables we won't seed at all
    SKIP_TABLES = {
        "asset_parts",
        "proposal_standard_map",
        "alignments",  # we already decided to skip
        "proposal_reviews",  # skip FK headache here too
        "work_order_parts",  # NEW: don't seed children of work_orders
        "work_order_tasks",  # NEW
        "work_order_time_logs"  # NEW
    }

    # FK relationships we do NOT want the patcher to "fix"
    BLOCKED_FKS = {
        ("maintenance_requests", "converted_work_order_id"),
        # NOTE: work_order_* FKs removed here so they CAN be patched.
    }

    # -----------------------------------------------------------------
    # Initial rows
    # -----------------------------------------------------------------
    for tname in order:
        if tname in SKIP_TABLES:
            data[tname] = []
            continue

        t = tables[tname]
        row: Dict[str, Any] = {}

        # Per-table exclusions (e.g. created_at tsvector)
        excluded_cols = set()
        if tname in TSVECTOR_CREATED_AT_TABLES:
            excluded_cols.add("created_at")

        for col in t.columns:
            # Skip real tsvector cols anywhere
            if is_tsvector_col(col):
                continue

            # Skip known-excluded cols (tsvector created_at, etc.)
            if col.name in excluded_cols:
                continue

            row[col.name] = sample_value(t, col, enums)

        # Table-specific hacks
        if tname == "bus_stop_times":
            row["arrival_time"] = "08:00:00"
            row["departure_time"] = "08:10:00"

        if tname == "maintenance_requests":
            row["converted_work_order_id"] = None

        # NOTE: we NO LONGER force work_order_id = None here.
        # FK patcher will later attach these to the seeded work_orders row.

        data[tname] = [row]

    # -----------------------------------------------------------------
    # Patch FK references (except the ones we've explicitly blocked)
    # -----------------------------------------------------------------
    for tname in order:
        if tname not in fk_map:
            continue
        if not data.get(tname):
            continue

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
    # Final safety scrub: ensure no created_at leaked into tsvector tables
    # -----------------------------------------------------------------
    for tname in TSVECTOR_CREATED_AT_TABLES:
        if tname in data:
            for row in data[tname]:
                row.pop("created_at", None)

    return data


# ---------------------------------------------------------------------
# Main Entry
# ---------------------------------------------------------------------
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

    # Correct call: only two arguments
    order = compute_insert_order(tables, fks)
    data = build_seed(tables, fks, order, enums)

    payload = {"insert_order": order, "data": data}

    with open(OUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"✔️ Seed file generated:\n{OUT_JSON_PATH}")
    print(f"✔️ Tables: {len(order)}")
    print(f"✔️ Enums detected: {sorted(enums.keys())}")


if __name__ == "__main__":
    main()
