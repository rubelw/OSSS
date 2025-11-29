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


# --- numeric coercion for bad numeric fields -------------------------
def coerce_numeric(value: Any, default: float = 0.0) -> float:
    """
    Make sure a value is a float. If it's junk (like 'kEEEfQ'), return default.
    """
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    if s == "" or s.upper() == "NULL":
        return default

    try:
        return float(s)
    except Exception:
        pass

    # try to salvage digits from the string, e.g. "$123.45"
    digits = "".join(ch for ch in s if (ch.isdigit() or ch == "."))
    if digits:
        try:
            return float(digits)
        except Exception:
            pass

    return default
# --------------------------------------------------------------------


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
        print(
            "Usage: python csv_to_seed_json.py <csv_dir> <out_json> "
            "[--uuid-mode=deterministic|random]"
        )
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

            # Ensure id is a proper UUID
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

            # Normalize *_id columns to UUIDs
            for k, v in list(r2.items()):
                if k.endswith("_id") and v not in (None, "", "NULL"):
                    if not is_uuid_like(str(v)):
                        r2[k] = coerce_uuid(v, table=table, column=k)

            # work_orders cost fields must be numeric
            if table == "work_orders":
                for cost_col in ("materials_cost", "labor_cost", "other_cost"):
                    if cost_col in r2:
                        r2[cost_col] = coerce_numeric(r2.get(cost_col), default=0.0)

            # requirements.created_at is tsvector in DB – don't send timestamp
            if table == "requirements":
                if "created_at" in r2:
                    r2.pop("created_at", None)

            # education_associations.created_at is also tsvector – drop it
            if table == "education_associations":
                if "created_at" in r2:
                    r2.pop("created_at", None)

            processed.append(r2)

        data[table] = processed

    # Fix asset_id FK for work_orders
    safe_asset_id = None
    if "assets" in data and data["assets"]:
        safe_asset_id = data["assets"][0].get("id")

    if "work_orders" in data:
        for row in data["work_orders"]:
            if safe_asset_id is not None:
                row["asset_id"] = safe_asset_id
            else:
                row["asset_id"] = None

    # family_portal_access: fix guardian_id & student_id FKs
    safe_guardian_id = None
    safe_student_id = None
    if "guardians" in data and data["guardians"]:
        safe_guardian_id = data["guardians"][0].get("id")
    if "students" in data and data["students"]:
        safe_student_id = data["students"][0].get("id")

    if "family_portal_access" in data:
        for row in data["family_portal_access"]:
            row["guardian_id"] = safe_guardian_id
            row["student_id"] = safe_student_id

    # guardians: student_user_id is NOT NULL – point to a real users.id
    safe_user_id = None
    if "users" in data and data["users"]:
        safe_user_id = data["users"][0].get("id")

    if "guardians" in data:
        if safe_user_id is None:
            # If we don't have any users to point at, don't seed guardians at all
            print("[csv_to_seed_json] No users found; dropping guardians to avoid NOT NULL FK issues.")
            data["guardians"] = []
        else:
            for row in data["guardians"]:
                if not row.get("student_user_id"):
                    row["student_user_id"] = safe_user_id

    # team_messages: ensure team_id references existing team
    safe_team_id = None
    if "teams" in data and data["teams"]:
        safe_team_id = data["teams"][0].get("id")

    if "team_messages" in data:
        if safe_team_id is None:
            print("[csv_to_seed_json] No teams found; dropping team_messages to avoid FK issues.")
            data["team_messages"] = []
        else:
            for row in data["team_messages"]:
                row["team_id"] = safe_team_id

    # work_assignments: ensure worker_id + event_id reference real rows
    safe_worker_id = None
    safe_event_id = None
    if "workers" in data and data["workers"]:
        safe_worker_id = data["workers"][0].get("id")
    if "events" in data and data["events"]:
        safe_event_id = data["events"][0].get("id")

    if "work_assignments" in data:
        if safe_worker_id is None or safe_event_id is None:
            print("[csv_to_seed_json] Missing workers or events; dropping work_assignments to avoid FK issues.")
            data["work_assignments"] = []
        else:
            for row in data["work_assignments"]:
                row["worker_id"] = safe_worker_id
                row["event_id"] = safe_event_id

    # journal_entry_lines + payroll_runs should point at a *real* journal_entry
    safe_journal_entry_id = None
    if "journal_entries" in data and data["journal_entries"]:
        safe_journal_entry_id = data["journal_entries"][0].get("id")

    if "journal_entry_lines" in data:
        for row in data["journal_entry_lines"]:
            row["entry_id"] = safe_journal_entry_id

    if "payroll_runs" in data:
        for row in data["payroll_runs"]:
            row["posted_entry_id"] = safe_journal_entry_id

    # ---- HARD FIX: drop accounting tables that keep causing FK issues ----
    for t in ("journal_entries", "journal_entry_lines", "gl_account_balances", "payroll_runs"):
        if t in data:
            print(f"[csv_to_seed_json] Removing table {t} from payload to avoid FK issues.")
            data[t] = []  # keep key but with no rows

    payload = {"insert_order": insert_order, "data": data}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=False)
    print(f"Wrote {out_json} with {len(insert_order)} table(s).")


if __name__ == "__main__":
    main()
