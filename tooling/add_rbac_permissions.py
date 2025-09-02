#!/usr/bin/env python3
import json, sys, pathlib

NEEDLE = "read:channels"
ADDED  = "read:subscriptions"

def fix_positions(node: dict) -> int:
    """Return how many position permission lists were updated under this node."""
    changed = 0
    # positions at this level
    for pos in node.get("positions", []) or []:
        perms = pos.get("permissions")
        if isinstance(perms, list) and NEEDLE in perms and ADDED not in perms:
            perms.append(ADDED)
            changed += 1
    # descend into children
    for child in node.get("children", []) or []:
        if isinstance(child, dict):
            changed += fix_positions(child)
    return changed

def main(path: str):
    p = pathlib.Path(path)
    data = json.loads(p.read_text())
    total = 0
    # file root may have a 'hierarchy' array
    for unit in data.get("hierarchy", []) or []:
        total += fix_positions(unit)
    # write back (pretty)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"Updated {total} position(s).")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: add_subscriptions_perm.py RBAC.json", file=sys.stderr)
        sys.exit(2)
    main(sys.argv[1])
