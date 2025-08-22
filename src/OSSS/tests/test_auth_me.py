# src/OSSS/tests/test_auth_me.py
def test_me_requires_auth(client):
    r = client.get("/me")
    assert r.status_code == 401
    assert "Bearer" in r.headers.get("www-authenticate", "")

def test_me_with_auth(client):
    r = client.get("/me", headers={"Authorization": "Bearer good"})
    assert r.status_code == 200
    body = r.json()
    assert body["preferred_username"] == "tester"
    assert body["aud"] == ["osss-api"]
