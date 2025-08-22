import os
import pytest
from starlette.testclient import TestClient
from fastapi import Header, HTTPException, status

from OSSS.main import app
from OSSS.core.config import settings

# --- Global test env ---
@pytest.fixture(scope="session", autouse=True)
def _env():
    os.environ.setdefault("KEYCLOAK_BASE_URL", "http://localhost:8085")
    os.environ.setdefault("KEYCLOAK_REALM", "OSSS")
    os.environ.setdefault("KEYCLOAK_CLIENT_ID", "osss-api")
    os.environ.setdefault("KEYCLOAK_CLIENT_SECRET", "changeme")
    os.environ.setdefault("KEYCLOAK_ALLOWED_AUDIENCES", "osss-api,osss-web")
    os.environ.setdefault("SKIP_DB_PING", "1")  # skip real DB ping during tests
    yield

# --- Fake auth dependency: accept Bearer good ---
def _fake_require_auth(authorization: str | None = Header(default=None, alias="Authorization")) -> dict:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": 'Bearer'},
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    if token != "good":
        raise HTTPException(status_code=401, detail="invalid token")
    return {
        "active": True,
        "sub": "user-123",
        "preferred_username": "tester",
        "email": "tester@example.com",
        "aud": ["osss-api"],
        "azp": "osss-web",
        "iss": f'{os.environ["KEYCLOAK_BASE_URL"].rstrip("/")}/realms/{os.environ["KEYCLOAK_REALM"]}',
        "realm_access": {"roles": ["user"]},
    }

# --- Fake DB session for /states so we don't touch a real DB ---
class _FakeResult:
    def __init__(self):
        self._rows = [{"code": "CA", "name": "California"}, {"code": "NY", "name": "New York"}]
    def mappings(self):
        return self
    def all(self):
        return self._rows
    def __iter__(self):
        return iter(self._rows)

class _FakeSession:
    async def execute(self, *a, **kw):
        return _FakeResult()
    async def close(self):  # called by dependency cleanup
        pass

async def _fake_get_session():
    sess = _FakeSession()
    try:
        yield sess
    finally:
        await sess.close()

@pytest.fixture()
def client():
    # Override dependencies
    from OSSS.auth import require_auth as real_require_auth
    from OSSS.db import get_session as real_get_session

    app.dependency_overrides[real_require_auth] = _fake_require_auth
    app.dependency_overrides[real_get_session] = _fake_get_session

    with TestClient(app) as c:
        yield c

    # Cleanup overrides (in case of other tests)
    app.dependency_overrides.pop(real_require_auth, None)
    app.dependency_overrides.pop(real_get_session, None)
