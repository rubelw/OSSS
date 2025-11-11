# src/OSSS/db/migrations/env.py
from __future__ import annotations

import os
import logging
from logging.config import fileConfig
from pathlib import Path
from alembic import context
from sqlalchemy import create_engine, pool, MetaData
from sqlalchemy.engine.url import make_url, URL
from urllib.parse import urlencode, urlsplit, urlunsplit, quote, parse_qs

config = context.config

# Logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

log = logging.getLogger("alembic.env")

# Import ONLY the metadata (avoid app side-effects)
try:
    from OSSS.models.base import Base
    target_metadata = Base.metadata
except Exception:  # pragma: no cover
    target_metadata = MetaData()

# Resolve paths relative to the repo (adjust if your layout differs in the container)
ROOT = Path(__file__).resolve().parents[4]
MAIN_VERSIONS = str(ROOT / "src" / "OSSS" / "db" / "migrations" / "versions")
TUTOR_VERSIONS = str(ROOT / "src" / "OSSS" / "db_tutor" / "migrations" / "versions")

# Pull version table names
TUTOR_VERSION_TABLE = config.get_main_option("tutor_version_table") or "alembic_version_tutor"
MAIN_VERSION_TABLE = config.get_main_option("version_table") or "alembic_version"


def _truthy(v: str | None) -> bool:
    return str(v).lower() in {"1", "true", "yes", "y", "on"}


xargs = context.get_x_argument(as_dictionary=True)

# Switches/inputs for tutor branch
TUTOR_SKIP = _truthy(xargs.get("tutor_skip")) or _truthy(os.getenv("TUTOR_SKIP"))
# Optional: allow passing tutor URL via -x; otherwise fall back to envs; otherwise None
TUTOR_URL_FROM_X = xargs.get("tutor_url")
TUTOR_URL = None if TUTOR_SKIP else (
    TUTOR_URL_FROM_X
    or os.getenv("TUTOR_DATABASE_URL")
    or os.getenv("TUTOR_DB_URL")
    or os.getenv("TUTOR_URL")
)

# ---------------------------------------------------------------------------
# URL helpers

def _rewrite_localhost_host(url_str: str) -> str:
    """
    If the DSN host is localhost/127.0.0.1/::1, rewrite to 'tutor-db:5432'
    so it works inside the container network. Opt-out with TUTOR_ALLOW_LOCALHOST=1.
    """
    if _truthy(os.getenv("TUTOR_ALLOW_LOCALHOST")):
        return url_str

    from urllib.parse import urlsplit, urlunsplit
    p = urlsplit(url_str)
    host = p.hostname or ""
    if host in {"localhost", "127.0.0.1", "::1"}:
        # keep userinfo and query/fragment; swap host:port only
        userinfo = ""
        if p.username:
            userinfo = p.username
            if p.password is not None:
                userinfo += ":" + p.password
            userinfo += "@"
        # Default to 5432 when rewriting
        new_netloc = f"{userinfo}tutor-db:5432"
        return urlunsplit((p.scheme, new_netloc, p.path, p.query, p.fragment))
    return url_str

def ensure_sync_url(url_str: str) -> str:
    """Force a sync driver (psycopg2) for Alembic, without masking the password."""
    u: URL = make_url(url_str)
    if u.get_backend_name() == "postgresql" and u.get_driver_name() in {"asyncpg", "aiopg", "psycopg"}:
        u = u.set(drivername="postgresql+psycopg2")
    if u.get_backend_name() == "postgresql" and (u.get_driver_name() in {None, ""}):
        u = u.set(drivername="postgresql+psycopg2")
    # DO NOT use str(u); it masks the password as ***
    return u.render_as_string(hide_password=False)


def encode_password_and_ssl(url_str: str) -> str:
    """
    Percent-encode password in DSN and ensure sslmode=disable if not set.
    Returns the literal DSN (no masking).
    """
    url_str = ensure_sync_url(url_str)

    p = urlsplit(url_str)

    # Rebuild netloc, encoding only the password (username left as-is)
    netloc = p.netloc
    userinfo, hostport = "", netloc
    if "@" in netloc:
        userinfo, hostport = netloc.split("@", 1)
    if userinfo:
        if ":" in userinfo:
            u, pw = userinfo.split(":", 1)
            userinfo = f"{u}:{quote(pw, safe='')}"
        netloc = f"{userinfo}@{hostport}"
    else:
        netloc = hostport

    # Ensure sslmode present (don’t override if already set)
    q = {k: (v[0] if isinstance(v, list) else v) for k, v in parse_qs(p.query).items()}
    q.setdefault("sslmode", "disable")
    query = urlencode(q)

    return urlunsplit((p.scheme, netloc, p.path, query, p.fragment))


def choose_url() -> tuple[str, str]:
    """
    Return (raw_url, source). Do NOT normalize here—callers will.
    """
    x = context.get_x_argument(as_dictionary=True)
    if x.get("sqlalchemy_url"):
        return x["sqlalchemy_url"], "-x sqlalchemy_url"

    env_candidates = (
        "ALEMBIC_DATABASE_URL",
        "DATABASE_URL",
        "SQLALCHEMY_DATABASE_URL",
        "ASYNC_DATABASE_URL",
        "OSSS_DATABASE_URL",
        "OSSS_DB_URL",
    )
    for name in env_candidates:
        v = os.getenv(name)
        if v:
            return v, f"env:{name}"

    ini_url = config.get_main_option("sqlalchemy.url")
    if ini_url:
        return ini_url, "alembic.ini sqlalchemy.url"

    # Final fallback (explicit string; no SQLAlchemy URL objects here)
    host = os.getenv("OSSS_DB_HOST", "localhost")
    port = os.getenv("OSSS_DB_PORT", "5432")
    name = os.getenv("OSSS_DB_NAME", "osss")
    user = os.getenv("OSSS_DB_USER", "osss")
    pwd = os.getenv("OSSS_DB_PASSWORD", "password")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{name}", "OSSS_DB_* fallback"


def choose_tutor_url() -> str | None:
    """
    Return raw tutor DB URL if present, else None.
    We check several common env var names used in your .env.
    """
    candidates = (
        "TUTOR_DB_URL",                # preferred if you set it
        "TUTOR_ALEMBIC_DATABASE_URL",  # present in your .env
        "OSSS_TUTOR_DB_URL",           # present in your .env
        "TUTOR_DATABASE_URL",          # present in your .env
        "TUTOR_ASYNC_DATABASE_URL",    # present in your .env (normalized to psycopg2)
    )
    for name in candidates:
        v = os.getenv(name)
        if v:
            return v
    return None


def _print_url(src: str, raw: str, url: str) -> None:
    """
    Print the chosen URL and its source to stdout so it’s visible even if logging is quiet.
    """
    print(f"[alembic-env] URL source: {src}")
    print(f"[alembic-env] URL raw (may be async): {raw}")
    print(f"[alembic-env] URL normalized (sync/encoded): {url}")

# Optional CLI toggles: -x echo=true -x log=DEBUG
_x = context.get_x_argument(as_dictionary=True)
if _x.get("echo", "").lower() in {"1", "true", "yes"}:
    config.set_main_option("sqlalchemy.echo", "true")

lvl = _x.get("log", "").upper()
if lvl in {"DEBUG", "INFO", "WARNING", "ERROR"}:
    logging.getLogger("alembic").setLevel(lvl)
    logging.getLogger("sqlalchemy.engine").setLevel(lvl)

# ---------------------------------------------------------------------------
# Core run helpers

def _run_once_online(raw_url: str, *, version_table: str, versions_path: str) -> None:
    """
    Normalize DSN and run a migration pass scoped to exactly one versions directory.
    Ensures both script_location and version_locations are set for this pass.
    """
    # Normalize/encode URL
    url = encode_password_and_ssl(raw_url)

    # Guard against masked passwords
    if urlsplit(raw_url).password == "***" or urlsplit(url).password == "***":
        raise RuntimeError("Masked password (***) detected in DSN. Pass the real secret, not the masked value.")

    # Temporarily set script_location + version_locations to this branch only
    original_script = config.get_main_option("script_location")
    original_vl = config.get_main_option("version_locations")
    try:
        config.set_main_option("script_location", versions_path)        # needed by Alembic core
        config.set_main_option("version_locations", versions_path)      # make env scan only here

        # Log what we’re about to use
        _print_url("scoped-pass", raw_url, url)
        log.info("Running ONLINE migrations in %s (version_table=%s)", versions_path, version_table)

        engine = create_engine(url, pool_pre_ping=True, poolclass=pool.NullPool, future=True)
        with engine.connect() as connection:
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
        # Restore config
        if original_script is None:
            config.remove_main_option("script_location")
        else:
            config.set_main_option("script_location", original_script)
        if original_vl is None:
            config.remove_main_option("version_locations")
        else:
            config.set_main_option("version_locations", original_vl)


def run_migrations_offline() -> None:
    raw, src = choose_url()
    url = encode_password_and_ssl(raw)

    # Guard: fail fast if a masked password ('***') slipped in
    if urlsplit(raw).password == "***" or urlsplit(url).password == "***":
        raise RuntimeError("Masked password (***) detected in DSN. Pass the real secret, not the masked value.")

    log.debug("URL source: %s", src)
    log.debug("URL raw (may be async): %s", raw)
    log.debug("URL normalized (sync/encoded): %s", url)
    log.info("Running OFFLINE migrations using %s", url)

    # Scope to MAIN only in offline mode
    original_script = config.get_main_option("script_location")
    original_vl = config.get_main_option("version_locations")
    try:
        config.set_main_option("script_location", MAIN_VERSIONS)
        config.set_main_option("version_locations", MAIN_VERSIONS)

        context.configure(
            url=url,
            target_metadata=target_metadata,
            literal_binds=True,
            compare_type=True,
            compare_server_default=True,
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


def run_migrations_online() -> None:
    # MAIN pass
    raw_main, _src = choose_url()
    _run_once_online(raw_main, version_table=MAIN_VERSION_TABLE, versions_path=MAIN_VERSIONS)

    # TUTOR pass (optional)
    if not TUTOR_SKIP:
        raw_tutor = TUTOR_URL or choose_tutor_url()
        if raw_tutor:
            # 🔒 rewrite localhost to service DNS if necessary
            raw_tutor = _rewrite_localhost_host(raw_tutor)
            _run_once_online(raw_tutor, version_table=TUTOR_VERSION_TABLE, versions_path=TUTOR_VERSIONS)
        else:
            log.info("Tutor migrations skipped (no tutor URL provided).")
    else:
        log.info("Tutor migrations skipped due to TUTOR_SKIP.")

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
