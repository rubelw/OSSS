# tests/conftest.py
"""
Boot a disposable Keycloak + two Postgres containers with docker compose for tests.

What this does:
- Builds realm-export.json (unless FK_SKIP_REALM_BUILD=1)
- Brings up docker-compose stack (Compose v2 or v1)
- Waits for **osss_postgres** TCP (localhost:5433) and applies Alembic migrations
- Waits for Keycloak OIDC discovery to be ready
- Tears everything down at session end (down -v) if we started it

Env knobs (useful ones):
- FK_COMPOSE_FILE       : compose file (default: <repo>/docker-compose.yml)
- FK_BOOT_WAIT          : seconds to wait for Keycloak (default: 90)
- FK_SKIP_INFRA         : skip compose up/down if set
- FK_OIDC_URL           : OIDC discovery URL to poll for readiness
- FK_SKIP_REALM_BUILD   : skip running build_realm.py
- FK_REALM_BUILDER      : path to build_realm.py
- FK_REALM_EXPORT       : path for realm-export.json

Alembic/DB (targets **osss_postgres** only):
- FK_DB_URL             : full SQLAlchemy URL (overrides all below)
- FK_DB_HOST            : default 'localhost'
- FK_DB_PORT            : default '5433' (published by osss_postgres)
- FK_DB_USER            : default 'oss'
- FK_DB_PASSWORD        : default 'oss'
- FK_DB_NAME            : default 'oss'
- FK_DB_BOOT_WAIT       : seconds to wait for TCP (default: 60)
- FK_SKIP_ALEMBIC       : skip migrations if set
- ALEMBIC_INI           : default <repo>/alembic.ini
- ALEMBIC_DIR           : default <repo>/alembic
"""

from __future__ import annotations
import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
import socket
from http.client import RemoteDisconnected
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# ---------------------------------------------------------------------------
# Repo root & realm build
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]

REALM_BUILDER = Path(os.getenv("FK_REALM_BUILDER", REPO_ROOT / "build_realm.py"))
REALM_EXPORT = Path(os.getenv("FK_REALM_EXPORT", REPO_ROOT / "realm-export.json"))
SKIP_REALM_BUILD = os.getenv("FK_SKIP_REALM_BUILD", "0").lower() in {"1", "true", "yes"}

def _run_realm_builder() -> None:
    """Run build_realm.py to (re)generate realm-export.json before starting KC."""
    if SKIP_REALM_BUILD:
        print("⚠️  FK_SKIP_REALM_BUILD=1 — skipping build_realm.py")
        return
    if not REALM_BUILDER.exists():
        raise SystemExit(f"build_realm.py not found at: {REALM_BUILDER}")

    py = shutil.which("python") or shutil.which("python3")
    if not py:
        raise SystemExit("Python not found on PATH; cannot run build_realm.py")

    print(f"🧱 Building realm export via: {py} {REALM_BUILDER}")
    res = subprocess.run(
        [py, "-u", str(REALM_BUILDER)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        if res.stdout:
            print(res.stdout)
        if res.stderr:
            print(res.stderr, file=sys.stderr)
        raise SystemExit("build_realm.py failed; aborting tests.")

    if not REALM_EXPORT.exists() or REALM_EXPORT.stat().st_size == 0:
        raise SystemExit(f"Realm export missing/empty at: {REALM_EXPORT}")
    print(f"✅ Realm export ready at {REALM_EXPORT}")

# ---------------------------------------------------------------------------
# Compose & Keycloak config
# ---------------------------------------------------------------------------

COMPOSE_FILE = os.getenv("FK_COMPOSE_FILE") or str(REPO_ROOT / "docker-compose.yml")
BOOT_WAIT = int(os.getenv("FK_BOOT_WAIT", "90"))
SKIP = os.getenv("FK_SKIP_INFRA")

DEFAULT_ENV = {
    # These are for the **Keycloak** DB (kc_postgres) in many examples; harmless to leave.
    "POSTGRES_USER": os.getenv("POSTGRES_USER", "kc"),
    "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD", "kcpassword"),
    "POSTGRES_DB": os.getenv("POSTGRES_DB", "keycloak"),
}

OIDC_DISCOVERY = os.getenv(
    "FK_OIDC_URL",
    "http://localhost:8085/realms/OSSS/.well-known/openid-configuration",
)

# ---------------------------------------------------------------------------
# Alembic / app DB targeting **osss_postgres**
# ---------------------------------------------------------------------------
# Defaults match the compose service:
#   osss_postgres:
#     ports: ["5433:5432"]
#     env: POSTGRES_DB=oss, POSTGRES_USER=oss, POSTGRES_PASSWORD=oss
DB_HOST = os.getenv("FK_DB_HOST", "localhost")
DB_PORT = int(os.getenv("FK_DB_PORT", "5433"))
DB_USER = os.getenv("FK_DB_USER", "oss")
DB_PASSWORD = os.getenv("FK_DB_PASSWORD", "oss")
DB_NAME = os.getenv("FK_DB_NAME", "oss")
DB_BOOT_WAIT = int(os.getenv("FK_DB_BOOT_WAIT", "60"))

DB_URL = os.getenv(
    "FK_DB_URL",
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
)

ALEMBIC_INI = Path(os.getenv("ALEMBIC_INI", REPO_ROOT / "alembic.ini"))
ALEMBIC_DIR = Path(os.getenv("ALEMBIC_DIR", REPO_ROOT / "alembic"))
SKIP_ALEMBIC = os.getenv("FK_SKIP_ALEMBIC", "0").lower() in {"1", "true", "yes"}

# ---------------------------------------------------------------------------
# Compose helpers
# ---------------------------------------------------------------------------

def _compose_base_cmd() -> list[str]:
    """Prefer `docker compose` (v2); fallback to `docker-compose` (v1)."""
    if shutil.which("docker"):
        try:
            res = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
            if res.returncode == 0:
                return ["docker", "compose"]
        except Exception:
            pass
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    raise SystemExit("Neither `docker compose` nor `docker-compose` is available on PATH.")

def _compose(*args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [*_compose_base_cmd(), "-f", COMPOSE_FILE, *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env or os.environ.copy(),
    )

# ---------------------------------------------------------------------------
# Wait / logs helpers
# ---------------------------------------------------------------------------

def _wait_for(url: str, timeout: int) -> bool:
    """Poll HTTP URL until 2xx or timeout."""
    deadline = time.time() + timeout
    delay = 1.5
    while time.time() < deadline:
        try:
            req = Request(url, method="GET", headers={"Connection": "close"})
            with urlopen(req, timeout=5) as r:
                if 200 <= r.status < 300:
                    return True
        except HTTPError as e:
            if 400 <= e.code < 500 and e.code not in (404,):
                pass
        except (URLError, RemoteDisconnected, ConnectionResetError, TimeoutError, socket.error):
            pass
        time.sleep(delay)
        delay = min(delay * 1.3, 4.0)
    return False

def _wait_for_tcp(host: str, port: int, timeout: int) -> bool:
    """Wait for a successful TCP connect to (host, port)."""
    deadline = time.time() + timeout
    delay = 1.0
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=3):
                return True
        except OSError:
            time.sleep(delay)
            delay = min(delay * 1.3, 4.0)
    return False

def _print_recent_logs(lines: int = 200) -> None:
    """Print recent docker-compose logs (all services)."""
    try:
        res = _compose("logs", "--tail", str(lines))
        if res.stdout:
            print(res.stdout)
        if res.stderr:
            print(res.stderr, file=sys.stderr)
    except Exception as e:
        print(f"(failed to fetch logs: {e})", file=sys.stderr)

# ---------------------------------------------------------------------------
# Alembic runner (targets **osss_postgres**)
# ---------------------------------------------------------------------------

def _run_alembic_upgrade() -> None:
    """
    Run `alembic upgrade head` against the **osss_postgres** DB.
    Skips cleanly if Alembic assets are missing or FK_SKIP_ALEMBIC=1.
    """
    if SKIP_ALEMBIC:
        print("⚠️  FK_SKIP_ALEMBIC=1 — skipping Alembic migrations")
        return
    if not ALEMBIC_DIR.exists():
        print(f"ℹ️  No {ALEMBIC_DIR} directory found — skipping Alembic migrations.")
        return
    if not ALEMBIC_INI.exists():
        print(f"ℹ️  No {ALEMBIC_INI} file found — skipping Alembic migrations.")
        return

    py = shutil.which("python") or shutil.which("python3")
    if not py:
        raise SystemExit("Python not found on PATH; cannot run Alembic")

    env = os.environ.copy()
    # Common env var names that env.py often reads
    env.setdefault("SQLALCHEMY_DATABASE_URL", DB_URL)
    env.setdefault("DATABASE_URL", DB_URL)
    env.setdefault("ALEMBIC_DATABASE_URL", DB_URL)
    # Also handy for any psql hooks in env.py
    env.setdefault("PGHOST", DB_HOST)
    env.setdefault("PGPORT", str(DB_PORT))
    env.setdefault("PGUSER", DB_USER)
    env.setdefault("PGPASSWORD", DB_PASSWORD)

    print(f"📦 Applying Alembic migrations to {DB_URL}")
    res = subprocess.run(
        [py, "-m", "alembic", "-c", str(ALEMBIC_INI), "upgrade", "head"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    if res.returncode != 0:
        if res.stdout:
            print(res.stdout)
        if res.stderr:
            print(res.stderr, file=sys.stderr)
        raise SystemExit("Alembic upgrade failed; aborting tests.")
    print("✅ Alembic migrations applied.")

# ---------------------------------------------------------------------------
# Pytest lifecycle
# ---------------------------------------------------------------------------

def pytest_sessionstart(session):
    """
    Order:
      0) (optional) Build realm-export.json
      1) docker compose up -d
      2) Wait for **osss_postgres** TCP (localhost:5433)
      3) Run Alembic migrations (upgrade head)
      4) Wait for Keycloak OIDC discovery
    """
    _run_realm_builder()

    if SKIP:
        print("⚠️  FK_SKIP_INFRA=1 set — skipping infra startup.")
        return

    if not Path(COMPOSE_FILE).exists():
        print(f"⚠️  Compose file not found at: {COMPOSE_FILE}. Skipping infra startup.")
        return

    env = os.environ.copy()
    env.update({k: v for k, v in DEFAULT_ENV.items() if k not in env})

    base_cmd = " ".join(_compose_base_cmd())
    print(f"▶️  Bringing up infra with: {base_cmd} -f {COMPOSE_FILE} up -d")
    res = _compose("up", "-d", env=env)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr, file=sys.stderr)
        raise SystemExit("docker compose up failed; aborting tests.")

    # Wait for the app DB (osss_postgres) — then migrate
    print(f"⏳ Waiting for Postgres (osss_postgres) at {DB_HOST}:{DB_PORT} (up to {DB_BOOT_WAIT}s)…")
    if not _wait_for_tcp(DB_HOST, DB_PORT, DB_BOOT_WAIT):
        print("❌ Postgres TCP not reachable in time. Recent logs:")
        _print_recent_logs(200)
        raise SystemExit("Postgres not reachable; aborting tests.")

    _run_alembic_upgrade()

    # Finally, wait for Keycloak
    print(f"⏳ Waiting for Keycloak OIDC at {OIDC_DISCOVERY} (up to {BOOT_WAIT}s)…")
    if not _wait_for(OIDC_DISCOVERY, BOOT_WAIT):
        print("❌ Keycloak did not become ready in time. Recent logs:")
        _print_recent_logs(200)
        raise SystemExit("Keycloak not ready; aborting tests.")

    session.config._fk_infra_started = True
    print("✅ Infra ready (osss_postgres migrated, Keycloak ready).")

def pytest_sessionfinish(session):
    """Tear down docker compose stack if we started it."""
    if SKIP or not getattr(session.config, "_fk_infra_started", False):
        return
    base_cmd = " ".join(_compose_base_cmd())
    print(f"🛑 Tearing down infra: {base_cmd} -f {COMPOSE_FILE} down -v")
    _compose("down", "-v")
