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

def _run_online(url: str, version_table: str, versions_path: str, *, tag: str | None = None) -> None:
    """
    Run one ONLINE pass scoped to a single versions dir + version table.
    We DO NOT touch script_location (must stay pointing at the env dir).
    """
    url2 = _encode_url(url)

    base_cfg = config.get_section(config.config_ini_section)
    cfg = dict(base_cfg) if base_cfg else {}
    cfg["sqlalchemy.url"] = url2

    # remember and temporarily narrow ONLY version_locations
    original_vl = config.get_main_option("version_locations")
    try:
        config.set_main_option("version_locations", versions_path)

        # (optional) show what Alembic sees from this lane
        sd = ScriptDirectory.from_config(config)
        heads = list(sd.get_heads())
        print(f"[alembic-env] versions_path={versions_path}")
        print(f"[alembic-env] discovered_heads={heads}")
        print(f"[alembic-env] url={url2}  version_table={version_table}")

        connectable = engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool, future=True)
        with connectable.connect() as connection:
            row = connection.exec_driver_sql(
                "select current_database(), current_user, current_schema, setting "
                "from pg_settings where name='search_path'"
            ).fetchone()
            print(f"[alembic-env] DB session: db={row[0]} user={row[1]} schema={row[2]} search_path={row[3]}")

            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
                version_table=version_table,
                version_locations=[versions_path],
                tag=tag,  # pass "tutor" when running tutor lane
            )
            print("[alembic-env] About to run migrations…")
            with context.begin_transaction():
                context.run_migrations()
    finally:
        if original_vl is None:
            config.remove_main_option("version_locations")
        else:
            config.set_main_option("version_locations", original_vl)

# ----- runners ---------------------------------------------------------------

def run_migrations_offline() -> None:
    # Disable offline to avoid silent no-ops
    raise RuntimeError("Offline migrations disabled. Run online only.")

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
        # explicit CLI override ALWAYS wins for tutor
        if override_url:
            tutor_url = override_url
            print("[alembic-env] TUTOR using CLI override sqlalchemy_url")
        else:
            if _truthy(os.getenv("TUTOR_SKIP")):
                print("[alembic-env] TUTOR skipped (TUTOR_SKIP=1)")
                tutor_url = None
            else:
                tutor_url = _choose_tutor_url(_choose_main_url())

        if not tutor_url:
            print("[alembic-env] TUTOR skipped (no tutor URL)")
        else:
            vt = config.get_main_option("tutor_version_table") or "alembic_version_tutor"
            print(f"[alembic-env] TUTOR chosen_url={tutor_url!r} vt={vt}")
            _run_online(tutor_url, vt, TUTOR_VERSIONS, tag="tutor")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
