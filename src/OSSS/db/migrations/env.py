from __future__ import annotations
import os
from pathlib import Path
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from urllib.parse import urlsplit, urlunsplit, urlencode, parse_qs, quote
from alembic.script import ScriptDirectory
import sys

print(f"[alembic-env] loaded: {__file__}", file=sys.stderr)

# Alembic Config object
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import metadata (optional for --autogenerate; safe if absent)
try:
    from OSSS.db.models import Base as CoreBase
except Exception:
    CoreBase = None
try:
    from OSSS.db_tutor.models import Base as TutorBase
except Exception:
    TutorBase = None

target_metadata = [m.metadata for m in (CoreBase, TutorBase) if m is not None] or None

# ----- paths (relative to THIS env.py) ---------------------------------------

ENV_DIR = Path(__file__).resolve().parent                  # .../src/OSSS/db/migrations
MAIN_VERSIONS = str(ENV_DIR / "versions")                  # .../src/OSSS/db/migrations/versions
TUTOR_VERSIONS = str(ENV_DIR.parent.parent / "db_tutor" / "migrations" / "versions")
# (script_location stays as configured in alembic.ini; do NOT override it globally)

# ----- helpers ---------------------------------------------------------------

def _xargs():
    return context.get_x_argument(as_dictionary=True)

def _which_branch() -> str:
    # 'core' (default) | 'tutor' | 'both'
    which = _xargs().get("only", "").strip().lower()
    return which if which in {"core", "tutor", "both"} else "core"


def _encode_url(url_str: str) -> str:
    """Force psycopg2 + percent-encode password + add sslmode=disable if missing."""
    p = urlsplit(url_str)
    # ensure driver
    scheme = p.scheme
    if scheme == "postgresql" or scheme.startswith("postgresql+"):
        if "+psycopg2" not in scheme:
            scheme = "postgresql+psycopg2"
    # encode password only
    netloc = p.netloc
    if "@" in netloc:
        userinfo, hostport = netloc.split("@", 1)
        if ":" in userinfo:
            u, pw = userinfo.split(":", 1)
            userinfo = f"{u}:{quote(pw, safe='')}"
        netloc = f"{userinfo}@{hostport}"
    # ensure sslmode
    q = {k: (v[0] if isinstance(v, list) else v) for k, v in parse_qs(p.query).items()}
    q.setdefault("sslmode", "disable")
    query = urlencode(q)
    return urlunsplit((scheme, netloc, p.path, query, p.fragment))

# --- add this helper (near _xargs / _encode_url helpers) --------------------
def _cli_sqlalchemy_url_override() -> str | None:
    x = context.get_x_argument(as_dictionary=True)
    val = x.get("sqlalchemy_url") or x.get("url")
    return val

# --- add this offline runner -----------------------------------------------
def _run_offline(url: str, version_table: str, versions_path: str) -> None:
    """
    Render SQL (offline) for a single branch/versions dir + version table.
    """
    url2 = _encode_url(url)

    original_script = config.get_main_option("script_location")
    original_vl = config.get_main_option("version_locations")
    try:
        # limit discovery to this branch
        config.set_main_option("script_location", versions_path)
        config.set_main_option("version_locations", versions_path)

        print(f"[alembic-env] OFFLINE versions_path={versions_path}")
        print(f"[alembic-env] OFFLINE url={url2}  version_table={version_table}")

        context.configure(
            url=url2,
            target_metadata=target_metadata,
            literal_binds=True,
            include_schemas=True,
            version_table=version_table,
        )
        with context.begin_transaction():
            context.run_migrations()
    finally:
        if original_script is None:
            config.remove_main_option("script_location")
        else:
            config.set_main_option("script_location", original_script)

        if original_vl is None:
            config.remove_main_option("version_locations")
        else:
            config.set_main_option("version_locations", original_vl)

def _choose_main_url() -> str:
    # NOTE: CLI -x sqlalchemy_url is NOT used for core; keep env-driven behavior for core.
    for k in ("DATABASE_URL","ALEMBIC_DATABASE_URL","SQLALCHEMY_DATABASE_URL","OSSS_DB_URL","OSSS_DATABASE_URL"):
        v = os.getenv(k)
        if v:
            return v
    return "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"

# ---- add below _choose_main_url() ------------------------------------------
def _truthy(v: str | None) -> bool:
    return str(v).lower() in {"1", "true", "yes", "y", "on"}

def _choose_tutor_url(main_url: str) -> str | None:
    """
    Pick the tutor DB URL unless TUTOR_SKIP is set.
    Falls back to main_url if no tutor-specific var is set.
    """
    if _truthy(os.getenv("TUTOR_SKIP")):
        return None

    # Try common env names you’ve been using
    for k in (
        "TUTOR_DB_URL",
        "TUTOR_ALEMBIC_DATABASE_URL",
        "OSSS_TUTOR_DB_URL",
        "TUTOR_DATABASE_URL",
        "TUTOR_ASYNC_DATABASE_URL",   # will be normalized by _encode_url()
    ):
        v = os.getenv(k)
        if v:
            return v
    return main_url

# (Optional) if you want to allow using localhost when run outside containers:
def _rewrite_localhost_host(url_str: str) -> str:
    """
    If not running in containers or when explicitly allowed, return url as-is.
    Otherwise this can be used to rewrite localhost to service DNS.
    Not used by default; call if needed.
    """
    return url_str

def _choose_tutor_url_favor_x() -> str | None:
    """
    Prefer CLI -x sqlalchemy_url for tutor runs. If absent, use TUTOR_* envs.
    Do NOT silently fall back to main unless explicitly allowed.
    """
    x = _xargs()
    url = x.get("sqlalchemy_url")
    if url:
        return url

    for k in (
        "TUTOR_DB_URL",
        "TUTOR_ALEMBIC_DATABASE_URL",
        "OSSS_TUTOR_DB_URL",
        "TUTOR_DATABASE_URL",
        "TUTOR_ASYNC_DATABASE_URL",
    ):
        v = os.getenv(k)
        if v:
            return v

    # Optional fallback to main if caller wants it:
    if _truthy(os.getenv("TUTOR_FALLBACK_TO_MAIN")):
        return _choose_main_url()

    return None


def _run_online(url: str, version_table: str, versions_path: str, tag: str | None = None) -> None:
    """
    Run one ONLINE pass, scoping Alembic to exactly one versions directory
    and one version table. Restores config afterward.
    """
    url2 = _encode_url(url)

    base_cfg = config.get_section(config.config_ini_section)
    cfg = dict(base_cfg) if base_cfg else {}
    cfg["sqlalchemy.url"] = url2

    # Derive a proper migrations root from the versions_path
    # (.../db_tutor/migrations/versions -> .../db_tutor/migrations)
    migrations_root = str(Path(versions_path).parent)

    original_script = config.get_main_option("script_location")
    original_vl = config.get_main_option("version_locations")
    try:
        # ✅ Point Alembic at the migrations ROOT, not the versions folder
        config.set_main_option("script_location", migrations_root)
        # ✅ Still restrict discovery to exactly this versions folder
        config.set_main_option("version_locations", versions_path)

        sd = ScriptDirectory.from_config(config)
        heads = list(sd.get_heads())
        print(f"[alembic-env] versions_path={versions_path}")
        print(f"[alembic-env] discovered_heads={heads}")
        print(f"[alembic-env] url={url2}  version_table={version_table}")

        connectable = engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool, future=True)
        try:
            with connectable.connect() as connection:
                row = connection.exec_driver_sql(
                    "select current_database(), current_user, current_schema, setting "
                    "from pg_settings where name='search_path'"
                ).fetchone()
                print(f"[alembic-env] DB session: db={row[0]} user={row[1]} schema={row[2]} search_path={row[3]}")
                print(f"[alembic-env] CONNECT OK -> {url2}", file=sys.stderr)

                context.configure(
                    connection=connection,
                    target_metadata=target_metadata,
                    compare_type=True,
                    compare_server_default=True,
                    version_table=version_table,
                    # pass a marker the revision can read *if* you still want it
                    tag=tag,
                )
                print("[alembic-env] About to run migrations…")
                with context.begin_transaction():
                    context.run_migrations()
        finally:
            connectable.dispose()
    finally:
        if original_script is None:
            config.remove_main_option("script_location")
        else:
            config.set_main_option("script_location", original_script)

        if original_vl is None:
            config.remove_main_option("version_locations")
        else:
            config.set_main_option("version_locations", original_vl)

# ----- runners ---------------------------------------------------------------

def run_migrations_offline() -> None:
    which = _which_branch()
    if which != "tutor":
        # keep offline disabled for core
        raise RuntimeError("Offline migrations enabled only for tutor. Run online for core.")

    # choose URL (CLI override wins)
    cli_url = _cli_sqlalchemy_url_override()
    chosen = cli_url or _choose_tutor_url(_choose_main_url())
    if not chosen:
        raise RuntimeError("No URL for tutor branch (offline). Provide -x sqlalchemy_url=...")

    vt = config.get_main_option("tutor_version_table") or "alembic_version_tutor"
    _run_offline(chosen, vt, TUTOR_VERSIONS)

def run_migrations_online() -> None:
    x = _xargs()
    which = (x.get("only", "") or "core").lower()
    if which not in {"core", "tutor", "both"}:
        which = "core"

    override_url = x.get("sqlalchemy_url")

    # ---- CORE ----
    if which in {"core", "both"}:
        core_url = override_url or _choose_main_url()
        vt = config.get_main_option("version_table") or "alembic_version"
        print(f"[alembic-env] CORE chosen_url={core_url!r} vt={vt}")
        _run_online(core_url, vt, MAIN_VERSIONS)

    # ---- TUTOR ----
    if which in {"tutor", "both"}:
        tutor_url = _choose_tutor_url(_choose_main_url())
        if not tutor_url:
            print("[alembic-env] TUTOR skipped (no tutor URL)")
        else:
            vt = config.get_main_option("tutor_version_table") or "alembic_version_tutor"
            print(f"[alembic-env] TUTOR url: {tutor_url}  version_table={vt}")
            _run_online(tutor_url, vt, TUTOR_VERSIONS, tag="tutor")

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()



