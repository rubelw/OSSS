import os
import pytest
from starlette.testclient import TestClient
from fastapi import Header, HTTPException, status
from OSSS.auth import require_auth as real_require_auth
from OSSS.auth.deps import oauth2 as real_oauth2
from fastapi.routing import APIRoute


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
def _fake_require_auth(authorization: str | None = Header(None, alias="Authorization")) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing bearer token", headers={"WWW-Authenticate": "Bearer"})
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != "good":
        raise HTTPException(status_code=401, detail="invalid token")
    return {"preferred_username": "tester", "aud": ["osss-api"], "sub": "user-123"}

async def _fake_oauth2(authorization: str | None = Header(None, alias="Authorization")) -> dict:
    return _fake_require_auth(authorization)

app.dependency_overrides[real_require_auth] = _fake_require_auth
app.dependency_overrides[real_oauth2] = _fake_oauth2

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
    def allow_all_security(*args, **kwargs) -> dict:
        # Accepts any request as an authenticated principal
        return {
            "active": True,
            "sub": "user-123",
            "preferred_username": "tester",
            "email": "tester@example.com",
            "aud": ["osss-api"],
            "azp": "osss-web",
            "iss": f'{os.environ.get("KEYCLOAK_BASE_URL","http://localhost:8085").rstrip("/")}/realms/{os.environ.get("KEYCLOAK_REALM","OSSS")}',
            "realm_access": {"roles": ["user"]},
        }

    overrides = []

    # 1) Blanket overrides for common guards (keeps things easy for most routes)
    for where in (
        ("OSSS.auth", "require_auth"),
        ("OSSS.auth.deps", "oauth2"),
        ("OSSS.api.security", "require_auth"),
        ("OSSS.api.security", "oauth2"),
        ("OSSS.api.security", "require_principal"),
        ("OSSS.api.security", "require_user"),
        ("OSSS.api.auth", "require_auth"),
        ("OSSS.api.deps", "oauth2"),
    ):
        mod_path, name = where
        try:
            mod = __import__(mod_path, fromlist=[name])
            dep = getattr(mod, name, None)
            if dep is not None:
                app.dependency_overrides[dep] = allow_all_security
                overrides.append(dep)
        except Exception:
            pass

    # 2) Route-targeted override: whatever /me or /debug/me depend on, replace it
    def _override_route_deps(path: str):
        for r in app.routes:
            if isinstance(r, APIRoute) and r.path == path and "GET" in (r.methods or []):
                for d in r.dependant.dependencies:
                    if d.call is not None:
                        app.dependency_overrides[d.call] = allow_all_security
                        overrides.append(d.call)

    for p in ("/me", "/debug/me"):
        _override_route_deps(p)

    # 3) Fake DB session if needed elsewhere (optional)
    class _FakeResult:
        def __init__(self):
            self._rows = [{"code": "CA", "name": "California"}, {"code": "NY", "name": "New York"}]
        def mappings(self): return self
        def all(self): return self._rows
        def __iter__(self): return iter(self._rows)
    class _FakeSession:
        async def execute(self, *a, **kw): return _FakeResult()
        async def close(self): pass
    async def _fake_get_session():
        sess = _FakeSession()
        try:
            yield sess
        finally:
            await sess.close()
    try:
        from OSSS.db import get_session as dep
        app.dependency_overrides[dep] = _fake_get_session
        overrides.append(dep)
    except Exception:
        pass

    with TestClient(app) as c:
        yield c

    # Cleanup
    for dep in overrides:
        app.dependency_overrides.pop(dep, None)