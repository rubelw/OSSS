# src/OSSS/tests/test_health.py
def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
