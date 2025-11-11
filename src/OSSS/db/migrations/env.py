from __future__ import annotations
import os
from pathlib import Path
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from urllib.parse import urlsplit, urlunsplit, urlencode, parse_qs, quote

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
# (script_location stays as configured in alembic.ini; do NOT override it here)

# ----- helpers ---------------------------------------------------------------

def _truthy(v: str | None) -> bool:
    return str(v).lower() in {"1", "true", "yes", "y", "on"}

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
    for k in ("DATABASE_URL","ALEMBIC_DATABASE_URL","SQLALCHEMY_DATABASE_URL","OSSS_DB_URL","OSSS_DATABASE_URL"):
        v = os.getenv(k)
        if v: return v
    return "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"

def _choose_tutor_url(main_url: str) -> str | None:
    if _truthy(os.getenv("TUTOR_SKIP")):
        return None
    for k in ("TUTOR_DB_URL","TUTOR_ALEMBIC_DATABASE_URL","OSSS_TUTOR_DB_URL","TUTOR_DATABASE_URL","TUTOR_ASYNC_DATABASE_URL"):
        v = os.getenv(k)
        if v: return v
    # fallback to main if none provided
    return main_url

def _run_online(url: str, version_table: str, versions_path: str) -> None:
    """
    Run one online pass, scoping Alembic to exactly one versions/ directory
    and one version table. We do NOT touch script_location.
    """
    url2 = _encode_url(url)

    # Base config for engine_from_config
    cfg = config.get_section(config.config_ini_section)
    if url2:
        cfg = dict(cfg)
        cfg["sqlalchemy.url"] = url2

    # Temporarily narrow discovery to this branch only
    original_vl = config.get_main_option("version_locations")
    try:
        config.set_main_option("version_locations", versions_path)

        print(f"[alembic-env] versions_path={versions_path} version_table={version_table}")
        print(f"[alembic-env] url={url2}")

        connectable = engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool, future=True)
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
                version_table=version_table,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        # restore version_locations to whatever it was (possibly unset)
        if original_vl is None:
            config.remove_main_option("version_locations")
        else:
            config.set_main_option("version_locations", original_vl)

# ----- runners ---------------------------------------------------------------

def run_migrations_offline() -> None:
    # Disable offline to avoid silent no-ops
    raise RuntimeError("Offline migrations disabled. Run online only.")

def run_migrations_online() -> None:
    # MAIN (uses version_table from alembic.ini or default)
    main_url = _choose_main_url()
    main_vt = config.get_main_option("version_table") or "alembic_version"
    print(f"[alembic-env] MAIN url: {main_url}  version_table={main_vt}")
    _run_online(main_url, main_vt, MAIN_VERSIONS)

    # TUTOR (falls back to main if TUTOR_* not set)
    tutor_url = _choose_tutor_url(main_url)
    if tutor_url:
        tutor_vt = config.get_main_option("tutor_version_table") or "alembic_version_tutor"
        print(f"[alembic-env] TUTOR url: {tutor_url}  version_table={tutor_vt}")
        _run_online(tutor_url, tutor_vt, TUTOR_VERSIONS)
    else:
        print("[alembic-env] TUTOR skipped")

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
