"""Populate pm_work_generators from CSV (robust plan lookup + **extra debug logging** + plan_name→plan_id + deep diagnostics)."""

from __future__ import annotations

import os, csv, logging, re, json
from pathlib import Path
from datetime import datetime
from contextlib import nullcontext

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# ---- Alembic identifiers ----
revision = "0054_populate_pm_work_gen"
down_revision = "0053_populate_doc_vers"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

# ---- Verbosity toggles (env-driven) ----
LOG_LVL = os.getenv("PM_GEN_LOG_LEVEL", "INFO").upper()
LOG_ROWS = os.getenv("PM_GEN_LOG_ROWS", "0") == "1"             # log every row at INFO
LOG_INDEX = os.getenv("PM_GEN_LOG_INDEX", "0") == "1"           # dump many index keys
ABORT_IF_ZERO = os.getenv("PM_GEN_ABORT_IF_ZERO", "0") == "1"   # raise if nothing inserted
VERIFY_EVERY = os.getenv("PM_GEN_VERIFY_EVERY", "0") == "1"     # run counts after each insert (expensive)

# New toggles
PLAN_COUNTS = os.getenv("PM_GEN_PLAN_COUNTS", "0") == "1"       # per-plan pre/post counts + deltas
EXPLAIN_QRY = os.getenv("PM_GEN_EXPLAIN", "0") == "1"           # EXPLAIN the verification SELECT
LOG_PRIVS   = os.getenv("PM_GEN_LOG_PRIVS", "0") == "1"         # log table owner & grants
DUMP_ROW    = os.getenv("PM_GEN_DUMP_ROW", "0") == "1"          # dump inserted row as JSON

logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
logging.getLogger("sqlalchemy.engine").setLevel(getattr(logging, LOG_LVL, logging.INFO))

PLANS_TBL = "pm_plans"
GEN_TBL   = "pm_work_generators"

CSV_NAME_GENERATORS = "pm_work_generators.csv"
CSV_NAME_PLANS      = "pm_plans.csv"  # optional – used for extra hints only

_norm_ws_re = re.compile(r"\s+")
_norm_non_alnum = re.compile(r"[^a-z0-9]+")

def _norm_key(s: str | None) -> str:
    if not s:
        return ""
    s = s.replace("\\ufeff", "").strip().lower()
    s = _norm_ws_re.sub(" ", s)
    return s

def _flat(s: str | None) -> str:
    return _norm_non_alnum.sub("", _norm_key(s))

def _digits(s: str | None) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())

def _find_csv(name: str, envvar: str | None = None) -> Path | None:
    here = Path(__file__).resolve()
    for p in [
        here.with_name(name),
        here.parent / "data" / name,
        here.parent.parent / "data" / name,
        Path(os.getenv(envvar or "", "")),
        Path.cwd() / name,
        Path("/mnt/data") / name,
    ]:
        if p and str(p) and Path(p).exists():
            log.info("[%s] using CSV: %s", revision, p)
            return Path(p)
    log.warning("[%s] CSV %s not found in standard locations", revision, name)
    return None

def _parse_bool(s: str | None) -> bool | None:
    if s is None: return None
    v = str(s).strip().lower()
    if v in ("1","t","true","y","yes"): return True
    if v in ("0","f","false","n","no"): return False
    return None

def _parse_dt(s: str | None):
    if not s: return None
    v = str(s).strip()
    if not v: return None
    try:
        if v.endswith("Z"): v = v[:-1]
        return datetime.fromisoformat(v)
    except Exception:
        return None

def _uuid_sql(bind) -> str:
    for name in ("gen_random_uuid", "uuid_generate_v4"):
        try:
            if bind.execute(sa.text("SELECT 1 FROM pg_proc WHERE proname=:n"), {"n": name}).scalar():
                log.info("[%s] using %s()", revision, name)
                return f"{name}()"
        except Exception:
            pass
    log.warning("[%s] no native UUID helper found; assuming gen_random_uuid()", revision)
    return "gen_random_uuid()"

def _outer_tx(conn):
    try:
        if hasattr(conn, "get_transaction") and conn.get_transaction() is not None:
            return nullcontext()
        if hasattr(conn, "in_transaction") and conn.in_transaction():
            return nullcontext()
    except Exception:
        return nullcontext()
    return conn.begin()

def _per_row_tx(conn):
    try:
        return conn.begin_nested()
    except Exception:
        return nullcontext()

def _open_csv(csv_path: Path):
    raw = csv_path.read_text(encoding="utf-8", errors="ignore")
    sample = raw.splitlines(True)[:10]
    try:
        dialect = csv.Sniffer().sniff("".join(sample), delimiters=",\\t;|")
    except Exception:
        dialect = csv.get_dialect("excel")
    f = csv_path.open("r", encoding="utf-8", newline="")
    return csv.DictReader(f, dialect=dialect), f

def _table_count(bind, table: str) -> int:
    try:
        return int(bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)
    except Exception:
        log.exception("[%s] failed to count rows for table %s", revision, table)
        return -1

# ---- Diagnostics ------------------------------------------------------------

def _log_connection_diagnostics(bind):
    try:
        row = bind.execute(sa.text(
            "SELECT current_database() AS db, current_user AS usr, "
            "current_schema() AS schema, current_setting('search_path') AS search_path"
        )).mappings().first()
        if row:
            log.info("[%s] DB=%s user=%s schema=%s search_path=%s", revision, row["db"], row["usr"], row["schema"], row["search_path"])
    except Exception:
        log.exception("[%s] failed to read connection diagnostics", revision)

def _log_table_privs(bind, table: str):
    if not LOG_PRIVS:
        return
    try:
        owner = bind.execute(sa.text("""
            SELECT pg_catalog.pg_get_userbyid(c.relowner) AS owner, n.nspname AS schema
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE c.relname=:t AND n.nspname = ANY (current_schemas(true)) LIMIT 1
        """), {"t": table}).mappings().first()
        if owner:
            log.info("[%s] %s owner=%s schema=%s", revision, table, owner["owner"], owner["schema"])
        grants = bind.execute(sa.text("""
            SELECT grantee, privilege_type
            FROM information_schema.role_table_grants
            WHERE table_name=:t AND table_schema = ANY (current_schemas(true))
            ORDER BY grantee, privilege_type
        """), {"t": table}).mappings().all()
        if grants:
            log.info("[%s] %s grants: %s", revision, table, [(g["grantee"], g["privilege_type"]) for g in grants])
    except Exception:
        log.exception("[%s] failed to read owner/grants for %s", revision, table)

def _diag_table(bind, table: str):
    try:
        info = bind.execute(sa.text("""
            SELECT c.relkind, c.relpersistence, c.relrowsecurity, n.nspname AS schema, c.relname,
                   pg_catalog.pg_get_expr(c.relpartbound, c.oid) AS partbound,
                   EXISTS (SELECT 1 FROM pg_partitioned_table p WHERE p.partrelid=c.oid) AS is_partitioned
            FROM pg_class c
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE c.relname=:t AND n.nspname = ANY (current_schemas(true))
            LIMIT 1
        """), {"t": table}).mappings().first()
        log.info(
            "[%s] %s relkind=%s persistence=%s rls=%s schema=%s is_partitioned=%s partbound=%s",
            revision, table,
            info and info["relkind"], info and info["relpersistence"], info and info["relrowsecurity"],
            info and info["schema"], info and info["is_partitioned"], info and info["partbound"]
        )
    except Exception:
        log.exception("[%s] failed pg_class diagnostics for %s", revision, table)

    # children (if partitioned)
    try:
        parts = bind.execute(sa.text("""
            SELECT inhrelid::regclass::text AS child
            FROM pg_inherits i
            JOIN pg_class p ON p.oid=i.inhparent
            WHERE p.relname=:t
        """), {"t": table}).scalars().all()
        if parts:
            log.info("[%s] %s partitions (%d): %s", revision, table, len(parts), parts)
    except Exception:
        log.exception("[%s] failed to list partitions for %s", revision, table)

    # rules (use safe columns across PG versions)
    try:
        rules = bind.execute(sa.text("""
            SELECT rulename, definition
            FROM pg_rules
            WHERE tablename=:t
        """), {"t": table}).mappings().all()
        if rules:
            log.info("[%s] %s rules: %s", revision, table, [(r["rulename"], (r.get("definition") or "")[:120]) for r in rules])
    except Exception:
        log.exception("[%s] failed to list rules for %s", revision, table)

    # triggers
    try:
        trg = bind.execute(sa.text("""
            SELECT t.tgname, t.tgenabled
            FROM pg_trigger t
            JOIN pg_class c ON c.oid=t.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE c.relname=:t AND n.nspname = ANY (current_schemas(true)) AND NOT t.tgisinternal
        """), {"t": table}).mappings().all()
        if trg:
            log.info("[%s] %s triggers: %s", revision, table, [(x["tgname"], x["tgenabled"]) for x in trg])
    except Exception:
        log.exception("[%s] failed to list triggers for %s", revision, table)

    # RLS policies (handle both old/new column names)
    try:
        pols = bind.execute(sa.text("""
            SELECT policyname AS name, permissive AS polpermissive, cmd AS polcmd
            FROM pg_policies
            WHERE schemaname = ANY (current_schemas(true)) AND tablename = :t
        """), {"t": table}).mappings().all()
    except Exception:
        try:
            pols = bind.execute(sa.text("""
                SELECT polname AS name, polpermissive AS polpermissive, polcmd AS polcmd
                FROM pg_policies
                WHERE schemaname = ANY (current_schemas(true)) AND tablename = :t
            """), {"t": table}).mappings().all()
        except Exception:
            pols = []
            log.exception("[%s] failed to list RLS policies for %s", revision, table)
    if pols:
        log.info("[%s] %s RLS policies: %s", revision, table, [(p["name"], p["polcmd"], p["polpermissive"]) for p in pols])

    # indexes & constraints (short peek)
    try:
        idxs = bind.execute(sa.text("""
            SELECT indexname FROM pg_indexes
            WHERE schemaname = ANY (current_schemas(true)) AND tablename=:t
            ORDER BY indexname
        """), {"t": table}).scalars().all()
        cons = bind.execute(sa.text("""
            SELECT conname, contype
            FROM pg_constraint
            WHERE conrelid = (SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                              WHERE c.relname=:t AND n.nspname = ANY (current_schemas(true)) LIMIT 1)
        """), {"t": table}).mappings().all()
        if idxs:
            log.info("[%s] %s indexes: %s", revision, table, idxs[:10])
        if cons:
            log.info("[%s] %s constraints: %s", revision, table, [(c["conname"], c["contype"]) for c in cons][:10])
    except Exception:
        log.exception("[%s] failed to list indexes/constraints for %s", revision, table)

# -------- plan indexing + plan_name → id map --------------------------------

def _load_plan_index_and_name_maps(bind, insp):
    cols = {c["name"] for c in insp.get_columns(PLANS_TBL)}
    select_cols = ["id"]
    if "code" in cols:  select_cols.append("code")
    if "title" in cols: select_cols.append("title")
    if "name" in cols:  select_cols.append("name")

    q = sa.text(f"SELECT {', '.join(select_cols)} FROM {PLANS_TBL}")
    rows = bind.execute(q).mappings().all()

    index: dict[str, str] = {}
    name_to_id: dict[str, str] = {}
    sample_names, sample_codes = set(), set()

    for r in rows:
        pid = str(r["id"])
        code  = r.get("code")
        title = r.get("title") or r.get("name")

        if code:  sample_codes.add(code)
        if title: sample_names.add(title)

        keys = set()

        if title:
            nk = _norm_key(title); fk = _flat(title)
            keys.add(nk); keys.add(fk)
            d = _digits(title)
            if d:
                keys.add(d); keys.add(f"plan{d}"); keys.add(f"plan{d.zfill(3)}")
            if nk and nk not in name_to_id: name_to_id[nk] = pid
            if fk and fk not in name_to_id: name_to_id[fk] = pid

        if code:
            keys.add(_norm_key(code))
            keys.add(_flat(code))
            d2 = _digits(code)
            if d2:
                keys.add(f"plan{d2}")
                keys.add(f"plan{d2.zfill(3)}")

        for k in keys:
            if k and k not in index:
                index[k] = pid

    log.info("[%s] built plan-index: plans=%d keys=%d", revision, len(set(index.values())), len(index))
    log.debug("[%s] example plan names: %s", revision, sorted(list(sample_names))[:8])
    log.debug("[%s] example plan codes: %s", revision, sorted(list(sample_codes))[:8])
    if LOG_INDEX:
        log.info("[%s] index peek: %s", revision, list(index.items())[:50])
        log.info("[%s] name→id peek: %s", revision, list(name_to_id.items())[:20])
    return index, name_to_id

def _suggest(index: dict[str, str], query_keys: list[str], limit: int = 5) -> list[str]:
    qs_digits = [_digits(k) for k in query_keys if k]
    hits = []
    for k in index.keys():
        kdig = _digits(k)
        if any(d and d == kdig for d in qs_digits if d):
            hits.append(k)
        elif any((qk and k.find(qk) >= 0) for qk in query_keys):
            hits.append(k)
        if len(hits) >= limit:
            break
    return hits

# -------- column/key helpers -------------------------------------------------
PLAN_TITLE_KEYS = ["plan_name", "plan_title", "title", "name"]  # CSV provides plan_name
FREQ_VAL_KEYS   = ["frequency_value", "interval_value", "freq_val", "every"]
FREQ_UNIT_KEYS  = ["frequency_unit", "interval_unit", "freq_unit", "unit"]
NEXT_RUN_KEYS   = ["next_run_at", "next_run_on", "next_on", "start_at"]
ACTIVE_KEYS     = ["is_active", "active", "enabled"]
ATTR_KEYS       = ["attributes", "meta", "payload", "config"]

def _normalize_row(row: dict) -> dict:
    return {_norm_key(k): v for k, v in row.items()}

def _pick(row: dict, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in row and row[c] not in (None, "", "NULL", "null"):
            return str(row[c]).strip()
    return None

def _detect_plan_fk(insp) -> str:
    cols = {c["name"] for c in insp.get_columns(GEN_TBL)}
    for cand in ("plan_id", "pm_plan_id", "plan", "pm_plan"):
        if cand in cols:
            return cand
    for fk in insp.get_foreign_keys(GEN_TBL):
        if fk.get("referred_table") == PLANS_TBL and fk.get("constrained_columns"):
            return fk["constrained_columns"][0]
    return "plan_id"

def _count_for_plan(bind, plan_fk_col: str, plan_id: str, only_parent: bool) -> int | None:
    try:
        only = "ONLY " if only_parent else ""
        return bind.execute(sa.text(f"SELECT COUNT(*) FROM {only}{GEN_TBL} WHERE {plan_fk_col}=:pid"), {"pid": plan_id}).scalar()
    except Exception:
        log.exception("[%s] count failure (%sparent) for plan_id=%s", revision, "ONLY-" if only_parent else "", plan_id)
        return None

# -------- migration ----------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    _log_connection_diagnostics(bind)
    _diag_table(bind, GEN_TBL)
    _log_table_privs(bind, GEN_TBL)

    pre_plans = _table_count(bind, PLANS_TBL)
    pre_gens  = _table_count(bind, GEN_TBL)
    log.info("[%s] pre-state counts: %s=%s, %s=%s", revision, PLANS_TBL, pre_plans, GEN_TBL, pre_gens)

    existing = set(insp.get_table_names(schema=None))
    for t in (PLANS_TBL, GEN_TBL):
        if t not in existing:
            log.warning("[%s] table %r missing — abort.", revision, t)
            return

    gen_csv = _find_csv(CSV_NAME_GENERATORS, envvar="PM_WORK_GENERATORS_CSV_PATH")
    if not gen_csv:
        raise RuntimeError(f"[{revision}] {CSV_NAME_GENERATORS} not found")
    _ = _find_csv(CSV_NAME_PLANS, envvar="PM_PLANS_CSV_PATH")

    plan_index, name_to_id = _load_plan_index_and_name_maps(bind, insp)
    if not plan_index:
        log.error("[%s] plan_index is EMPTY — cannot map CSV rows to plan ids.", revision)

    gen_cols = {c["name"] for c in insp.get_columns(GEN_TBL)}
    log.info("[%s] %s columns detected: %s", revision, GEN_TBL, sorted(gen_cols))

    plan_fk_col = _detect_plan_fk(insp)
    log.info("[%s] using plan FK column on %s: %s", revision, GEN_TBL, plan_fk_col)

    has_created_at = "created_at" in gen_cols
    has_updated_at = "updated_at" in gen_cols

    uuid_sql = _uuid_sql(bind)

    col_map = {
        "frequency_value": "frequency_value" if "frequency_value" in gen_cols else ("interval_value" if "interval_value" in gen_cols else None),
        "frequency_unit": "frequency_unit" if "frequency_unit" in gen_cols else ("interval_unit" if "interval_unit" in gen_cols else None),
        "next_run_at": "next_run_at" if "next_run_at" in gen_cols else ("next_run_on" if "next_run_on" in gen_cols else None),
        "is_active": "is_active" if "is_active" in gen_cols else ("active" if "active" in gen_cols else ("enabled" if "enabled" in gen_cols else None)),
        "attributes": "attributes" if "attributes" in gen_cols else ("meta" if "meta" in gen_cols else None),
    }
    log.info("[%s] column map resolved: %s", revision, col_map)

    # dynamic INSERT + RETURNING tableoid
    ins_cols = ["id", plan_fk_col]
    ins_vals = [uuid_sql, f":plan_id"]
    active_params: set[str] = {"plan_id"}

    def add_col(db_col: str | None, param: str):
        if db_col:
            ins_cols.append(db_col)
            ins_vals.append(f":{param}")
            active_params.add(param)

    add_col(col_map["frequency_value"], "freq_val")
    add_col(col_map["frequency_unit"], "freq_unit")
    add_col(col_map["next_run_at"],     "next_run_at")
    add_col(col_map["is_active"],       "is_active")
    add_col(col_map["attributes"],      "attributes")

    if has_created_at:
        ins_cols.append("created_at"); ins_vals.append("now()")
    if has_updated_at:
        ins_cols.append("updated_at"); ins_vals.append("now()")

    base_ins_sql = f"INSERT INTO {GEN_TBL} ({', '.join(ins_cols)}) VALUES ({', '.join(ins_vals)})"
    ins_sql = base_ins_sql + " RETURNING id, tableoid::regclass::text AS dest_table"

    log.debug("[%s] INSERT SQL: %s", revision, ins_sql)
    log.debug("[%s] active params: %s", revision, sorted(active_params))

    ins = sa.text(ins_sql)
    if "attributes" in active_params:
        ins = ins.bindparams(sa.bindparam("attributes", type_=pg.JSONB))
    ins = ins.bindparams(sa.bindparam("plan_id"))
    if "freq_val" in active_params:    ins = ins.bindparams(sa.bindparam("freq_val"))
    if "freq_unit" in active_params:   ins = ins.bindparams(sa.bindparam("freq_unit"))
    if "next_run_at" in active_params: ins = ins.bindparams(sa.bindparam("next_run_at"))
    if "is_active" in active_params:   ins = ins.bindparams(sa.bindparam("is_active"))

    chk_exists = sa.text(f"SELECT 1 FROM {GEN_TBL} WHERE {plan_fk_col}=:pid LIMIT 1")

    # CSV head preview
    try:
        with open(gen_csv, "r", encoding="utf-8") as fh:
            head = [next(fh).rstrip("\\n") for _ in range(5)]
        log.info("[%s] %s head:\\n    %s", revision, getattr(gen_csv, "name", str(gen_csv)), "\\n    ".join(head))
    except Exception:
        log.exception("[%s] failed to preview CSV head", revision)

    inserted = skipped = missing = existed = 0
    total = 0

    reader, fobj = _open_csv(gen_csv)
    try:
        log.info("[%s] generators CSV header: %s", revision, reader.fieldnames)

        with _outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                total += 1
                row = _normalize_row(raw)

                # read plan_name from CSV
                plan_title_raw = _pick(row, PLAN_TITLE_KEYS)
                if LOG_ROWS:
                    log.info("[%s] row %d: plan_name/title=%r; raw=%r", revision, idx, plan_title_raw, raw)

                # candidate keys by name
                tried_keys = []
                k_title = _norm_key(plan_title_raw)
                f_title = _flat(plan_title_raw)
                d_title = _digits(plan_title_raw)
                for k in (k_title, f_title):
                    if k: tried_keys.append(k)
                if d_title:
                    tried_keys += [d_title, f"plan{d_title}", f"plan{d_title.zfill(3)}"]

                # resolve plan id
                plan_id = None
                matched_key = None
                for k in tried_keys:
                    plan_id = plan_index.get(k)
                    if plan_id:
                        matched_key = k
                        break

                if not plan_id and k_title:
                    try:
                        plan_id = bind.execute(
                            sa.text(
                                f"SELECT id FROM {PLANS_TBL} "
                                "WHERE lower(coalesce(title,name)) = :n LIMIT 1"
                            ),
                            {"n": k_title}
                        ).scalar()
                        if plan_id:
                            matched_key = f"=lower(title|name):{k_title}"
                    except Exception:
                        log.exception("[%s] row %d: direct SQL lookup by plan_name failed", revision, idx)

                if not plan_id:
                    hints = _suggest(plan_index, tried_keys, limit=5)
                    log.warning(
                        "[%s] row %d could not resolve plan_id via plan_name=%r; keys_tried=%r; suggestions=%r; plans_in_index=%d",
                        revision, idx, plan_title_raw, tried_keys, hints, len(set(plan_index.values()))
                    )
                    missing += 1
                    continue

                # idempotence
                try:
                    if bind.execute(chk_exists, {"pid": plan_id}).scalar():
                        existed += 1
                        if LOG_ROWS:
                            log.info("[%s] row %d: generator already exists for plan_id=%s (matched=%r)", revision, idx, plan_id, matched_key)
                        continue
                except Exception:
                    log.exception("[%s] row %d: existence check failed for plan_id=%s", revision, idx, plan_id)
                    # continue on — we will try to insert

                # payload
                freq_val = _pick(row, FREQ_VAL_KEYS)
                try:
                    freq_val = int(freq_val) if freq_val not in (None, "",) else None
                except Exception:
                    freq_val = None
                freq_unit = _pick(row, FREQ_UNIT_KEYS)
                next_run  = _parse_dt(_pick(row, NEXT_RUN_KEYS)) or datetime.utcnow()
                is_active = _parse_bool(_pick(row, ACTIVE_KEYS))
                attrs_raw = _pick(row, ATTR_KEYS)
                try:
                    attributes = json.loads(attrs_raw) if attrs_raw else None
                except Exception:
                    attributes = attrs_raw

                params = {"plan_id": plan_id}
                if "freq_val"    in active_params: params["freq_val"]    = freq_val
                if "freq_unit"   in active_params: params["freq_unit"]   = freq_unit
                if "next_run_at" in active_params: params["next_run_at"] = next_run
                if "is_active"   in active_params: params["is_active"]   = True if is_active is None else is_active
                if "attributes"  in active_params: params["attributes"]  = attributes

                # Pre-counts (safe defaults to avoid UnboundLocalError)
                pre_parent = pre_incl = None
                if PLAN_COUNTS:
                    try:
                        pre_parent = _count_for_plan(bind, plan_fk_col, plan_id, only_parent=True)
                        pre_incl  = _count_for_plan(bind, plan_fk_col, plan_id, only_parent=False)
                        log.info("[%s] row %d pre-counts plan_id=%s: ONLY_parent=%s, incl_parts=%s",
                                 revision, idx, plan_id, pre_parent, pre_incl)
                    except Exception:
                        log.exception("[%s] row %d: pre-counts failed for plan_id=%s", revision, idx, plan_id)

                # Do the insert in its own try/except so diagnostics cannot mark it as failed
                new_id = dest_table = None
                try:
                    with _per_row_tx(bind):
                        res = bind.execute(ins, params).mappings().first()
                        new_id = res and res.get("id")
                        dest_table = res and res.get("dest_table")
                    log.info("[%s] row %d INSERT RETURNING id=%s dest_table=%s plan_id=%s (matched=%r)",
                             revision, idx, new_id, dest_table, plan_id, matched_key)
                    inserted += 1
                except Exception:
                    skipped += 1
                    log.exception("[%s] row %d failed to insert; params=%r", revision, idx, params)
                    continue  # move to next row

                # Verification select (do not affect inserted counter)
                try:
                    ver_sql = sa.text(f"SELECT id FROM {GEN_TBL} WHERE {plan_fk_col}=:pid ORDER BY created_at DESC NULLS LAST, updated_at DESC NULLS LAST LIMIT 1")
                    ver = bind.execute(ver_sql, {"pid": plan_id}).scalar()
                    if not ver:
                        log.error("[%s] row %d VERIFICATION FAILED: cannot see inserted row for plan_id=%s (matched=%r dest=%s)",
                                  revision, idx, plan_id, matched_key, dest_table)
                    else:
                        log.debug("[%s] row %d verified id=%s for plan_id=%s", revision, idx, ver, plan_id)

                    if EXPLAIN_QRY:
                        try:
                            ex = bind.execute(sa.text(f"EXPLAIN (VERBOSE, COSTS FALSE) {ver_sql.text}"), {"pid": plan_id}).scalars().all()
                            log.info("[%s] row %d EXPLAIN verify SELECT: %s", revision, idx, " | ".join(ex))
                        except Exception:
                            log.exception("[%s] row %d: EXPLAIN failed", revision, idx)
                except Exception:
                    log.exception("[%s] row %d: verification select failed", revision, idx)

                # Post-counts & deltas (must not raise)
                if PLAN_COUNTS:
                    try:
                        post_parent = _count_for_plan(bind, plan_fk_col, plan_id, only_parent=True)
                        post_incl   = _count_for_plan(bind, plan_fk_col, plan_id, only_parent=False)
                        log.info("[%s] row %d post-counts plan_id=%s: ONLY_parent=%s, incl_parts=%s; deltas=(ONLY=%s,incl=%s)",
                                 revision, idx, plan_id, post_parent, post_incl,
                                 (None if post_parent is None or pre_parent is None else (post_parent - pre_parent)),
                                 (None if post_incl is None or pre_incl is None else (post_incl - pre_incl)))
                    except Exception:
                        log.exception("[%s] row %d: post-counts failed", revision, idx)

                # Optional dump of inserted row
                if DUMP_ROW and new_id:
                    try:
                        row_dump = bind.execute(sa.text(f"SELECT to_jsonb(t) FROM {GEN_TBL} t WHERE t.id=:id"), {"id": new_id}).scalar()
                        log.info("[%s] row %d inserted row JSON: %s", revision, idx, row_dump)
                    except Exception:
                        log.exception("[%s] row %d: failed to dump inserted row id=%s", revision, idx, new_id)

    finally:
        try:
            fobj.close()
        except Exception:
            pass

    # Post-state and samples
    try:
        cnt_parent_only = bind.execute(sa.text(f"SELECT COUNT(*) FROM ONLY {GEN_TBL}")).scalar()
    except Exception:
        cnt_parent_only = None
    post_gens = _table_count(bind, GEN_TBL)
    delta = (post_gens if isinstance(post_gens, int) else 0) - (pre_gens if isinstance(pre_gens, int) else 0)
    log.info("[%s] rows_in_csv=%d inserted=%d skipped=%d (missing=%d, existed=%d) — %s pre=%s post=%s delta=%s (ONLY parent=%s)",
             revision, total, inserted, skipped, missing, existed, GEN_TBL, pre_gens, post_gens, delta, cnt_parent_only)

    try:
        sample = bind.execute(sa.text(
            f"SELECT id, {plan_fk_col} AS plan_id, created_at, updated_at, tableoid::regclass::text AS src "
            f"FROM {GEN_TBL} ORDER BY created_at DESC NULLS LAST LIMIT 5"
        )).mappings().all()
        log.info("[%s] sample rows in %s (top 5 recent): %s", revision, GEN_TBL, sample)
    except Exception:
        log.exception("[%s] failed to fetch sample rows from %s", revision, GEN_TBL)

    if ABORT_IF_ZERO and inserted > 0 and (post_gens is not None) and delta <= 0:
        raise RuntimeError(f"[{revision}] Inserted {inserted} rows but table count did not increase (delta={delta}). Check schema/search_path, view/rules, RLS, or partitions.")

    if ABORT_IF_ZERO and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; inspect logs with PM_GEN_LOG_ROWS=1, PM_GEN_LOG_INDEX=1")

def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if GEN_TBL not in set(insp.get_table_names(schema=None)):
        log.info("[%s] downgrade: %s table missing; nothing to do.", revision, GEN_TBL)
        return

    plan_fk_col = _detect_plan_fk(insp)
    log.info("[%s] downgrade using plan FK column: %s", revision, plan_fk_col)

    gen_csv = _find_csv(CSV_NAME_GENERATORS)
    if not gen_csv:
        log.warning("[%s] downgrade: %s not found; skipping deletion.", revision, CSV_NAME_GENERATORS)
        return

    reader, fobj = _open_csv(gen_csv)
    try:
        plan_index, _ = _load_plan_index_and_name_maps(bind, insp)

        plan_ids = set()
        for raw in reader:
            row = _normalize_row(raw)
            plan_title_raw = _pick(row, PLAN_TITLE_KEYS)
            keys = []
            if plan_title_raw:
                k = _norm_key(plan_title_raw); f = _flat(plan_title_raw); d = _digits(plan_title_raw)
                keys.extend([k, f])
                if d: keys.extend([d, f"plan{d}", f"plan{d.zfill(3)}"])
            for k in keys:
                pid = plan_index.get(k)
                if pid:
                    plan_ids.add(pid); break

        if not plan_ids:
            log.info("[%s] downgrade: no matching plan_ids found from CSV; nothing to delete.", revision)
            return

        sample = list(plan_ids)[:10]
        log.info("[%s] downgrade: deleting generators for %d plans (sample=%s ...)",
                 revision, len(plan_ids), sample)

        del_sql = sa.text(f"DELETE FROM {GEN_TBL} WHERE {plan_fk_col} = ANY(:pids)")
        del_sql = del_sql.bindparams(sa.bindparam("pids", type_=pg.ARRAY(pg.UUID(as_uuid=False))))

        with _outer_tx(bind):
            result = bind.execute(del_sql, {"pids": list(plan_ids)})
            rc = getattr(result, "rowcount", None)
            log.info("[%s] downgrade: delete completed; rowcount=%s", revision, rc)

    finally:
        try:
            fobj.close()
        except Exception:
            pass
