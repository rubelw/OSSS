#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ---------- helpers ----------

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def load_records_from_file(p: Path) -> List[Dict[str, Any]]:
    """
    Load a list of row dicts from .json / .jsonl / .ndjson / .csv.
    - .json: if it's a list -> return it; if it's an object -> wrap into [obj].
    - .jsonl/.ndjson: one JSON object per line.
    - .csv: uses DictReader; all fields are strings unless you post-process.
    """
    suffix = p.suffix.lower()
    if suffix == ".json":
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        elif isinstance(data, dict):
            return [data]
        else:
            raise ValueError(f"{p} JSON is neither list nor object.")
    elif suffix in {".jsonl", ".ndjson"}:
        rows: List[Dict[str, Any]] = []
        with p.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    raise ValueError(f"{p}:{i} is not a JSON object.")
                rows.append(obj)
        return rows
    elif suffix == ".csv":
        with p.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            return [dict(row) for row in reader]
    else:
        raise ValueError(f"Unsupported file type: {p.name}")

def detect_seed_format(seed: Any) -> str:
    """
    Return "mapping" for {table: [rows]} format.
    Return "list" for [{"table"/"model": name, "rows"/"data": [...]}, ...].
    """
    if isinstance(seed, dict):
        # simple heuristic: values should be lists (rows)
        if all(isinstance(v, list) for v in seed.values()):
            return "mapping"
        return "mapping"  # still treat as mapping; user may be building up incrementally
    if isinstance(seed, list):
        # look for dict entries w/ "table"/"model"
        for item in seed:
            if isinstance(item, dict) and any(k in item for k in ("table", "model")):
                return "list"
    raise ValueError("Unrecognized seed format. Expected object {table:[...]} or list of entries.")

def get_list_entry(seed_list: List[Dict[str, Any]], table: str) -> Tuple[int, Dict[str, Any]] | Tuple[None, None]:
    """
    Find entry index & ref by "table" or "model" case-insensitive.
    """
    for i, entry in enumerate(seed_list):
        if not isinstance(entry, dict):
            continue
        name = (entry.get("table") or entry.get("model") or "").strip().lower()
        if name == table.lower():
            return i, entry
    return None, None

def append_rows(existing: List[Dict[str, Any]], new_rows: List[Dict[str, Any]], dedupe_key: str | None) -> List[Dict[str, Any]]:
    if not dedupe_key:
        return existing + new_rows
    seen = set()
    merged: List[Dict[str, Any]] = []
    # existing first
    for r in existing:
        key = r.get(dedupe_key)
        merged.append(r)
        seen.add(key)
    # then add new if not seen
    for r in new_rows:
        key = r.get(dedupe_key)
        if key not in seen:
            merged.append(r)
            seen.add(key)
    return merged

# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description="Update seed_full_school.json from old_data directory.")
    ap.add_argument(
        "--seed",
        default="src/OSSS/db/migrations/data/seed_full_school.json",
        help="Path to seed JSON to update (default: %(default)s)",
    )
    ap.add_argument(
        "--src",
        default="src/OSSS/db/migrations/old_data",
        help="Directory containing per-table seed files (default: %(default)s)",
    )
    ap.add_argument(
        "--mode",
        choices=["replace", "append"],
        default="replace",
        help="Replace (overwrite table rows) or append (merge rows). Default: replace",
    )
    ap.add_argument(
        "--dedupe-key",
        default=None,
        help="When --mode=append, de-duplicate by this field name if present (e.g., 'id').",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't write back to the seed file; just show what would change.",
    )
    args = ap.parse_args()

    seed_path = Path(args.seed).resolve()
    src_dir = Path(args.src).resolve()

    if not seed_path.exists():
        eprint(f"[!] Seed file not found: {seed_path}")
        sys.exit(1)
    if not src_dir.is_dir():
        eprint(f"[!] Source directory not found: {src_dir}")
        sys.exit(1)

    with seed_path.open("r", encoding="utf-8") as f:
        try:
            seed = json.load(f)
        except json.JSONDecodeError as ex:
            eprint(f"[!] Could not parse seed JSON: {ex}")
            sys.exit(1)

    seed_fmt = detect_seed_format(seed)
    print(f"[INFO] Seed format: {seed_fmt}")

    # Gather table files (support .json, .jsonl/.ndjson, .csv)
    candidates = list(src_dir.glob("*.json")) + list(src_dir.glob("*.jsonl")) + \
                 list(src_dir.glob("*.ndjson")) + list(src_dir.glob("*.csv"))
    if not candidates:
        eprint(f"[!] No source files found under {src_dir}")
        sys.exit(1)

    changes = 0

    for p in sorted(candidates):
        table = p.stem  # filename without extension
        try:
            rows = load_records_from_file(p)
        except Exception as ex:
            eprint(f"[WARN] Skipping {p.name}: {ex}")
            continue

        if seed_fmt == "mapping":
            existing = seed.get(table)
            if args.mode == "replace" or existing is None:
                action = "REPLACED" if existing is not None else "ADDED"
                seed[table] = rows
                changes += 1
                print(f"[OK] {action} {table}: {len(rows)} row(s)")
            else:
                # append
                if not isinstance(existing, list):
                    eprint(f"[WARN] {table} exists but is not a list; replacing to maintain consistency.")
                    seed[table] = rows
                    changes += 1
                    print(f"[OK] REPLACED {table}: {len(rows)} row(s)")
                else:
                    seed[table] = append_rows(existing, rows, args.dedupe_key)
                    changes += 1
                    print(f"[OK] APPENDED {table}: +{len(rows)} row(s) -> total {len(seed[table])}")

        elif seed_fmt == "list":
            if not isinstance(seed, list):
                eprint("[!] Internal error: seed detected as list but not a list.")
                sys.exit(1)
            idx, entry = get_list_entry(seed, table)
            if idx is None:
                # create new entry with canonical keys
                new_entry = {"table": table, "rows": rows}
                seed.append(new_entry)
                changes += 1
                print(f"[OK] ADDED entry for {table}: {len(rows)} row(s)")
            else:
                # normalize rows key
                rows_key = "rows" if "rows" in entry else "data" if "data" in entry else None
                if rows_key is None:
                    # create canonical 'rows'
                    entry["rows"] = rows
                    if "data" in entry:
                        del entry["data"]
                    changes += 1
                    print(f"[OK] FIXED entry keys & REPLACED rows for {table}: {len(rows)} row(s)")
                else:
                    if args.mode == "replace":
                        entry[rows_key] = rows
                        changes += 1
                        print(f"[OK] REPLACED {table}: {len(rows)} row(s)")
                    else:
                        if not isinstance(entry[rows_key], list):
                            entry[rows_key] = rows
                            changes += 1
                            print(f"[OK] REPLACED malformed rows for {table}: {len(rows)} row(s)")
                        else:
                            entry[rows_key] = append_rows(entry[rows_key], rows, args.dedupe_key)
                            changes += 1
                            print(f"[OK] APPENDED {table}: +{len(rows)} row(s) -> total {len(entry[rows_key])}")
        else:
            eprint("[!] Unsupported seed format.")
            sys.exit(1)

    if changes == 0:
        print("[INFO] No changes made (nothing matched or all skipped).")
        return

    if args.dry_run:
        print(f"[DRY-RUN] Would write updates to: {seed_path}")
        return

    # Backup then write
    backup = seed_path.with_suffix(seed_path.suffix + ".bak")
    shutil.copy2(seed_path, backup)
    print(f"[INFO] Backup created: {backup}")

    with seed_path.open("w", encoding="utf-8") as f:
        json.dump(seed, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"[DONE] Updated seed written to: {seed_path}")

if __name__ == "__main__":
    main()
