# src/OSSS/tests/test_token_flow.py
import pytest
import requests

# Try these in order; remove the ones you don't use later
TOKEN_PATHS = ("/token", "/auth/token", "/api/token", "/v1/token")

def _post_token(client, payload):
    """Try POSTing as form first, then JSON, across candidate paths."""
    last = None
    # form-encoded
    for p in TOKEN_PATHS:
        resp = client.post(p, data=payload)
        last = resp
        if resp.status_code != 404:  # route found
            return resp
    # json
    for p in TOKEN_PATHS:
        resp = client.post(p, json=payload)
        last = resp
        if resp.status_code != 404:
            return resp
    return last

def _extract_access_token(data):
    if not isinstance(data, dict):
        return None
    if "access_token" in data:
        return data["access_token"]
    tok = data.get("token")
    if isinstance(tok, dict):
        return tok.get("access_token")
    return None

def _patch_token_http(monkeypatch, status_code, json_body=None, text=""):
    """Patch both requests and httpx (sync+async) to return a dummy token response."""
    json_body = json_body or {}

    class DummyResp:
        def __init__(self):
            self.status_code = status_code
            self._json = json_body
            self.text = text
        def json(self):
            return self._json

    # requests.post
    try:
        import requests
        monkeypatch.setattr(requests, "post", lambda *a, **kw: DummyResp())
    except Exception:
        pass

    # httpx.post and httpx.AsyncClient.post
    try:
        import httpx
        monkeypatch.setattr(httpx, "post", lambda *a, **kw: DummyResp())

        class DummyAsyncResp:
            def __init__(self):
                self.status_code = status_code
                self._json = json_body
                self.text = text
            def json(self):
                return self._json

        class DummyAsyncClient:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def post(self, *a, **kw): return DummyAsyncResp()

        monkeypatch.setattr(httpx, "AsyncClient", DummyAsyncClient)
    except Exception:
        pass

def test_password_grant_success(client, monkeypatch):
    # Simulate IdP/token endpoint success
    _patch_token_http(
        monkeypatch,
        status_code=200,
        json_body={"access_token": "abc", "refresh_token": "def", "token_type": "Bearer", "expires_in": 300},
    )

    payload = {"username": "ok", "password": "ok", "grant_type": "password"}
    r = _post_token(client, payload)
    assert r.status_code == 200

    body = r.json()
    assert _extract_access_token(body) == "abc"
    if isinstance(body, dict):
        assert "token_type" in body or "access_token" in body

def test_password_grant_failure(client, monkeypatch):
    # Simulate IdP/token endpoint failure
    _patch_token_http(
        monkeypatch,
        status_code=400,
        json_body={"error": "invalid_grant", "error_description": "Bad credentials"},
        text="Bad credentials",
    )

    payload = {"username": "bad", "password": "nope", "grant_type": "password"}
    r = _post_token(client, payload)

    # Apps vary: 400 (bad request from IdP) or 401/403 (your API mapping). Accept common ones.
    assert r.status_code in (400, 401, 403)

    # Body should indicate an error, or at least have text
    try:
        data = r.json()
        assert any(k in data for k in ("error", "detail", "message")) or r.text
    except Exception:
        assert r.text
