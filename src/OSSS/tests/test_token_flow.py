# src/OSSS/tests/test_token_flow.py
def test_password_grant_success(client, monkeypatch):
    import requests

    class DummyResp:
        status_code = 200
        def json(self):
            return {"access_token": "abc", "refresh_token": "def"}

    monkeypatch.setattr(requests, "post", lambda *a, **kw: DummyResp())
    r = client.post("/token", data={"username": "ok", "password": "ok"})
    assert r.status_code == 200
    assert "access_token" in r.json()

def test_password_grant_failure(client, monkeypatch):
    import requests

    class DummyResp:
        status_code = 400
        text = "Bad credentials"
        def json(self):
            return {}

    monkeypatch.setattr(requests, "post", lambda *a, **kw: DummyResp())
    r = client.post("/token", data={"username": "bad", "password": "nope"})
    assert r.status_code == 401

