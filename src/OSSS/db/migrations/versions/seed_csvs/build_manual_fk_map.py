#!/usr/bin/env python3
import re
import sys
from pathlib import Path
from pprint import pprint

table_re = re.compile(r"^Checking\s+([^\s]+)")
fail_re = re.compile(r"^\s*FAIL\s+(\w+)\s*->\s*([^.]+)\.(\w+)")

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: build_manual_fk_map.py <fk_validation_output.txt>", file=sys.stderr)
        sys.exit(1)

    log_path = Path(sys.argv[1])
    if not log_path.exists():
        print(f"[ERROR] File not found: {log_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Reading {log_path}", file=sys.stderr)

    manual_fk_map = {}
    current_table = None
    line_count = 0
    fail_count = 0

    with log_path.open() as f:
        for line in f:
            line_count += 1
            if line_count % 1000 == 0:
                print(f"[INFO] Processed {line_count} lines…", file=sys.stderr, flush=True)

            m_table = table_re.match(line)
            if m_table:
                current_table = m_table.group(1)
                print(f"[DEBUG] Now in table: {current_table}", file=sys.stderr, flush=True)
                continue

            m_fail = fail_re.match(line)
            if m_fail and current_table:
                child_col, parent_table, parent_col = m_fail.groups()
                table_map = manual_fk_map.setdefault(current_table, {})
                table_map[child_col] = (parent_table, parent_col)
                fail_count += 1
                print(
                    f"[DEBUG] Add FK: {current_table}.{child_col} -> {parent_table}.{parent_col}",
                    file=sys.stderr,
                    flush=True,
                )

    print(f"[INFO] Done. Processed {line_count} lines, found {fail_count} FK failures.",
          file=sys.stderr)

    print("\nMANUAL_FK_MAP = ")
    pprint(manual_fk_map, sort_dicts=True)

if __name__ == "__main__":
    main()
