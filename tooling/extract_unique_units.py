#!/usr/bin/env python3
"""
extract_unique_units.py

Recursively extract all 'unit' fields from a JSON file, convert to Start Case,
dedupe, and print to stdout (and/or write CSV/TXT/JSON files).

Usage:
  python extract_unique_units.py RBAC.json --csv units.csv --txt units.txt --json units.json
"""

from __future__ import annotations
import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from typing import Any

def start_case(value: str) -> str:
    """
    Convert a string to Start Case (title case with common separators normalized).
    Example: 'athletics_activities-enrichment' -> 'Athletics Activities Enrichment'
    """
    if not isinstance(value, str):
        return str(value)

    # Normalize separators to spaces and collapse whitespace
    s = re.sub(r"[_\-:/]+", " ", value.strip())
    s = re.sub(r"\s+", " ", s)

    # Title-case each word; keep all-caps acronyms as-is
    words = []
    for w in s.split(" "):
        if len(w) <= 3 and w.isupper():  # keep short acronyms (e.g., "K12", "SIS")
            words.append(w)
        else:
            words.append(w[:1].upper() + w[1:].lower())
    return " ".join(words)

def iter_key_values(obj: Any, key: str = "unit"):
    """
    Yield values for every occurrence of the given key anywhere in a nested structure.
    """
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            if k == key:
                yield v
            # Recurse into values
            yield from iter_key_values(v, key)
    elif isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        for item in obj:
            yield from iter_key_values(item, key)

def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    ap = argparse.ArgumentParser(description="Extract unique 'unit' values from JSON in Start Case.")
    ap.add_argument("input", help="Path to JSON file (e.g., RBAC.json)")
    ap.add_argument("--key", default="unit", help="Field name to extract (default: unit)")
    ap.add_argument("--no-sort", action="store_true", help="Preserve first-seen order (default: sort A→Z)")
    ap.add_argument("--csv", help="Write results to a CSV (one value per row)")
    ap.add_argument("--txt", help="Write results to a TXT (one value per line)")
    ap.add_argument("--json", dest="json_out", help="Write results to a JSON array")
    args = ap.parse_args()

    try:
        data = load_json(args.input)
    except Exception as e:
        print(f"Failed to read JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # Collect and normalize
    raw_values = list(iter_key_values(data, key=args.key))
    normalized = []
    for v in raw_values:
        if isinstance(v, (list, tuple)):
            for vv in v:
                normalized.append(start_case(str(vv)))
        else:
            normalized.append(start_case(str(v)))

    # Dedupe (preserve order) then sort unless --no-sort
    # dict.fromkeys keeps first occurrence order in Py3.7+
    unique = list(dict.fromkeys(normalized))
    if not args.no_sort:
        unique = sorted(unique, key=lambda s: s.lower())

    # Print to stdout
    print("\n".join(unique))

    # Optional outputs
    if args.csv:
        import csv
        with open(args.csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            for u in unique:
                writer.writerow([u])
    if args.txt:
        with open(args.txt, "w", encoding="utf-8") as f:
            f.write("\n".join(unique) + "\n")
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(unique, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
