#!/usr/bin/env python3
"""
Extract tables from a DBML file that do NOT have outbound foreign keys.

Usage:
    python find_tables_without_fks.py schema.dbml
"""

import re
import sys
from typing import Dict, Set, List


TABLE_REGEX = re.compile(
    r'(?m)^\s*Table\s+(`[^`]+`|"[^"]+"|\w+)\s*{'
)

# Matches lines like:
#   Ref: tableA.col > tableB.col
#   Ref: table_a.col - table_b.col
#   Ref: "Table A".col < "Table B".col
REF_LINE_REGEX = re.compile(
    r'(?m)^\s*Ref\s*:\s*(.+?)$'
)

# Operators in Ref: left <op> right
REF_OP_REGEX = re.compile(r'(.+?)\s*([<>-])\s*(.+)')

# Extract table name from "table.column" or `table`.`column`
TABLE_NAME_FROM_REF_SIDE = re.compile(
    r'^\s*(`[^`]+`|"[^"]+"|[A-Za-z_][A-Za-z0-9_]*)\s*\.'
)

# Inline column refs, e.g.:
#   student_id int [ref: > students.id]
#   some_id int [ref: - "Other Table".id]
INLINE_REF_REGEX = re.compile(r'\[.*?\bref:\s*([<>-])\s*([^\]]+)\]', re.IGNORECASE)


def normalize_table_name(name: str) -> str:
    """Remove quotes/backticks and trim whitespace."""
    name = name.strip()
    if (name.startswith('"') and name.endswith('"')) or \
       (name.startswith('`') and name.endswith('`')):
        name = name[1:-1]
    return name.strip()


def find_tables(dbml: str) -> Dict[str, str]:
    """
    Return dict of table_name -> table_body (the text inside the braces).
    """
    tables: Dict[str, str] = {}
    for match in TABLE_REGEX.finditer(dbml):
        raw_name = match.group(1)
        name = normalize_table_name(raw_name)
        start = match.end()  # position after '{'
        # We need to find the matching closing brace.
        brace_level = 1
        i = start
        while i < len(dbml) and brace_level > 0:
            if dbml[i] == '{':
                brace_level += 1
            elif dbml[i] == '}':
                brace_level -= 1
            i += 1
        body = dbml[start:i-1]
        tables[name] = body
    return tables


def parse_ref_line_left_fk_tables(line: str) -> Set[str]:
    """
    Given a 'Ref: ...' line content (without the 'Ref:' prefix),
    return the set of tables that have OUTBOUND FKs based on this line.
    """
    fk_tables: Set[str] = set()
    line = line.strip()
    m = REF_OP_REGEX.match(line)
    if not m:
        return fk_tables

    left_side, op, right_side = m.groups()

    def extract_table(side: str) -> str | None:
        m2 = TABLE_NAME_FROM_REF_SIDE.search(side)
        if not m2:
            return None
        return normalize_table_name(m2.group(1))

    left_table = extract_table(left_side)
    right_table = extract_table(right_side)

    # Direction:
    #   left > right  → left has FK to right
    #   left < right  → right has FK to left
    #   left - right  → treat both as having FKs (many-to-many or unspecified)
    if op == '>':
        if left_table:
            fk_tables.add(left_table)
    elif op == '<':
        if right_table:
            fk_tables.add(right_table)
    elif op == '-':
        if left_table:
            fk_tables.add(left_table)
        if right_table:
            fk_tables.add(right_table)

    return fk_tables


def find_tables_with_fk_from_global_refs(dbml: str) -> Set[str]:
    """
    Find tables that have outbound FKs defined in 'Ref:' lines.
    """
    tables_with_fk: Set[str] = set()
    for ref_match in REF_LINE_REGEX.finditer(dbml):
        ref_content = ref_match.group(1)  # everything after "Ref:"
        tables_with_fk |= parse_ref_line_left_fk_tables(ref_content)
    return tables_with_fk


def find_tables_with_fk_from_inline_refs(tables: Dict[str, str]) -> Set[str]:
    """
    Find tables that have outbound FKs defined inline in column definitions,
    e.g., [ref: > other_table.id] or [ref: - other_table.id].
    """
    tables_with_fk: Set[str] = set()

    for table_name, body in tables.items():
        for inline_match in INLINE_REF_REGEX.finditer(body):
            op = inline_match.group(1)
            # target = inline_match.group(2)  # we don't actually need target table here

            # Direction:
            #   >  = outbound FK
            #   -  = treat as outbound (usually a join table)
            #   <  = inbound only, do NOT mark as outbound
            if op in ('>', '-'):
                tables_with_fk.add(table_name)
                break  # one outbound FK is enough to mark this table

    return tables_with_fk


def main(path: str) -> None:
    with open(path, 'r', encoding='utf-8') as f:
        dbml = f.read()

    # 1. Parse tables
    tables = find_tables(dbml)
    all_table_names: Set[str] = set(tables.keys())

    # 2. Find tables that have outbound FKs (global refs + inline refs)
    fk_from_refs = find_tables_with_fk_from_global_refs(dbml)
    fk_from_inline = find_tables_with_fk_from_inline_refs(tables)

    tables_with_outbound_fk: Set[str] = fk_from_refs | fk_from_inline

    # 3. Tables without outbound FKs
    tables_without_fk: List[str] = sorted(all_table_names - tables_with_outbound_fk)

    print("# Tables without outbound foreign keys")
    for name in tables_without_fk:
        print(name)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python find_tables_without_fks.py schema.dbml", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
