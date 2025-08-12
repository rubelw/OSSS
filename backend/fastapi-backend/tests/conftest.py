import os
import sys
import pathlib
import pytest
import sqlalchemy as sa
from sqlalchemy.pool import StaticPool

# ------------------------------------------------------------------
# Locate the project root dynamically so `import app` works.
# We look upward for a directory that has "app/main.py".
# ------------------------------------------------------------------
HERE = pathlib.Path(__file__).resolve()
for parent in [HERE, *HERE.parents]:
    app_main = parent / "app" / "main.py"
    if app_main.exists():
        sys.path.insert(0, str(parent))
        break

# Optional: also honor an env var override
if "APP_PROJECT_ROOT" in os.environ:
    sys.path.insert(0, os.environ["APP_PROJECT_ROOT"])

from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def app():
    # Import the repo's FastAPI app
    from app.main import app as _app

    # ---- Override security dependencies (no-op auth) ----
    try:
        from app.auth import require_realm_roles
        _app.dependency_overrides[require_realm_roles] = lambda *_, **__: None
    except Exception:
        pass  # If not present, ignore

    # ---- Override DB dependency to use SQLite in-memory ----
    # Import Base
    try:
        from app.models.base import Base as ModelsBase
    except Exception:
        from app.models import Base as ModelsBase
    Base = ModelsBase

    # Create in-memory SQLite engine
    engine = sa.create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    # Create all tables
    Base.metadata.create_all(engine)

    # Session factory
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    # Try to find the repo's get_db dependency
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    overridden = False
    for candidate in ("app.db", "app.database", "app.dependencies.db", "app.dependencies"):
        try:
            mod = __import__(candidate, fromlist=["get_db"])
            if hasattr(mod, "get_db"):
                _app.dependency_overrides[mod.get_db] = override_get_db
                overridden = True
                break
        except Exception:
            continue
    if not overridden:
        try:
            import app
            if hasattr(app, "get_db"):
                _app.dependency_overrides[app.get_db] = override_get_db
        except Exception:
            pass

    return _app


@pytest.fixture(scope="session")
def client(app):
    return TestClient(app)

