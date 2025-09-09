#!/usr/bin/env python3
import os, sys, csv, json, uuid, re, pathlib
from typing import Any, Dict, List

UUID_MODE = "deterministic"
VALID_UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")

def is_uuid_like(s: str) -> bool:
    if not isinstance(s, str) or not VALID_UUID_RE.match(s):
        return False
    try:
        uuid.UUID(s)
        return True
    except Exception:
        return False

def coerce_uuid(value: Any, *, table: str, column: str) -> str:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        value = ""
    if isinstance(value, str) and is_uuid_like(value):
        return str(uuid.UUID(value))
    seed = f"{table}.{column}:{json.dumps(value, sort_keys=True, ensure_ascii=False)}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))

def maybe_parse_json_cell(text: str):
    if text is None:
        return None
    s = text.strip()
    if s == "":
        return None
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
        try:
            return int(s)
        except Exception:
            pass
    try:
        if "." in s:
            return float(s)
    except Exception:
        pass
    if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
        try:
            return json.loads(s)
        except Exception:
            pass
    return s

def load_csv_table(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            parsed = {k: maybe_parse_json_cell(v) for k, v in row.items()}
            rows.append(parsed)
    return rows

def main():
    if len(sys.argv) < 3:
        print("Usage: python csv_to_seed_json.py <csv_dir> <out_json> [--uuid-mode=deterministic|random]")
        sys.exit(2)
    csv_dir = sys.argv[1]
    out_json = sys.argv[2]
    global UUID_MODE
    if len(sys.argv) >= 4 and sys.argv[3].startswith("--uuid-mode"):
        mode = sys.argv[3].split("=")[-1].strip()
        if mode in ("deterministic", "random"):
            UUID_MODE = mode

    files = [p for p in os.listdir(csv_dir) if p.lower().endswith(".csv")]
    if not files:
        raise SystemExit("No CSV files found in " + csv_dir)

    def sort_key(name: str):
        m = re.match(r"^(\d+)_", name)
        if m:
            return (0, int(m.group(1)), name)
        return (1, 0, name)
    files.sort(key=sort_key)

    insert_order: List[str] = []
    data: Dict[str, List[Dict[str, Any]]] = {}

    for fname in files:
        table = re.sub(r"^\d+_", "", os.path.splitext(fname)[0])
        insert_order.append(table)
        rows = load_csv_table(os.path.join(csv_dir, fname))

        processed: List[Dict[str, Any]] = []
        for r in rows:
            r2 = dict(r)
            if "id" not in r2 or r2.get("id") in (None, "", "NULL"):
                if UUID_MODE == "random":
                    r2["id"] = str(uuid.uuid4())
                else:
                    seed = f"{table}:row:{json.dumps(r, sort_keys=True, ensure_ascii=False)}"
                    r2["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, seed))
            else:
                v = r2["id"]
                if not is_uuid_like(str(v)):
                    r2["id"] = coerce_uuid(v, table=table, column="id")

            for k, v in list(r2.items()):
                if k.endswith("_id") and v not in (None, "", "NULL"):
                    if not is_uuid_like(str(v)):
                        r2[k] = coerce_uuid(v, table=table, column=k)
            processed.append(r2)

        data[table] = processed

    payload = {"insert_order": insert_order, "data": data}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=False)
    print(f"Wrote {out_json} with {len(insert_order)} table(s).")

if __name__ == "__main__":
    main()
