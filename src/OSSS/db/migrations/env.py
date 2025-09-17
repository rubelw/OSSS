# src/OSSS/db/migrations/env.py
from __future__ import annotations

import os
import logging
from logging.config import fileConfig

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

# ---------------------------------------------------------------------------

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
    pwd  = os.getenv("OSSS_DB_PASSWORD", "password")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{name}", "OSSS_DB_* fallback"

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

def run_migrations_offline() -> None:
    raw, src = choose_url()
    url = encode_password_and_ssl(raw)

    # Guard: fail fast if a masked password ('***') slipped in
    from urllib.parse import urlsplit  # you already import this at top; keep or remove this line
    if urlsplit(raw).password == "***" or urlsplit(url).password == "***":
        raise RuntimeError("Masked password (***) detected in DSN. Pass the real secret, not the masked value.")

    # (rest unchanged)
    log.debug("URL source: %s", src)
    log.debug("URL raw (may be async): %s", raw)
    log.debug("URL normalized (sync/encoded): %s", url)
    log.info("Running OFFLINE migrations using %s", url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    raw, src = choose_url()
    url = encode_password_and_ssl(raw)

    # Guard: fail fast if a masked password ('***') slipped in
    from urllib.parse import urlsplit  # you already import this at top; keep or remove this line
    if urlsplit(raw).password == "***" or urlsplit(url).password == "***":
        raise RuntimeError("Masked password (***) detected in DSN. Pass the real secret, not the masked value.")

    # (rest unchanged)
    log.debug("URL source: %s", src)
    log.debug("URL raw (may be async): %s", raw)
    log.debug("URL normalized (sync/encoded): %s", url)
    log.info("Running ONLINE migrations using %s", url)
    engine = create_engine(url, pool_pre_ping=True, poolclass=pool.NullPool, future=True)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
