# src/OSSS/tests/test_state.py
def test_states_requires_auth(client):
    r = client.get("/states")
    assert r.status_code == 401

def test_states_with_auth(client):
    r = client.get("/states", headers={"Authorization": "Bearer good"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
