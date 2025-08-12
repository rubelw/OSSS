import json
import re

def _has_path(openapi, path):
    return path in (openapi.get("paths") or {})

def test_openapi_loads(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "paths" in data and isinstance(data["paths"], dict)
    # basic sanity: title + version present
    info = data.get("info", {})
    assert info.get("title"), "OpenAPI info.title missing"
    assert info.get("version"), "OpenAPI info.version missing"


def test_expected_routes_present(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()

    # Expect core and CIC routes if the corresponding add_crud calls were added
    expected_maybe = [
        "/districts",
        "/schools",
        "/cic_committees",
        "/cic_meetings",
        "/cic_agenda_items",
        "/cic_motions",
        "/cic_votes",
        "/cic_resolutions",
        "/cic_proposals",
        "/cic_proposal_reviews",
        "/cic_proposal_documents",
        "/cic_meeting_documents",
        "/cic_publications",
    ]

    # These are "maybe" because some may be behind different prefixes or not registered yet.
    # We assert at least one of the CIC endpoints exists to catch wiring mistakes.
    present = [p for p in expected_maybe if p in spec.get("paths", {})]
    assert present, "None of the expected CIC/Core routes were found in OpenAPI paths"


def test_list_endpoints_do_not_crash(client):
    """
    Iterate through GET collection endpoints that do not require path params
    and ensure they return a status code (200/204/401/403) rather than 500.
    """
    r = client.get("/openapi.json")
    spec = r.json()
    paths = spec.get("paths", {})

    checked = 0
    for path, methods in paths.items():
        if "{" in path:
            continue  # skip endpoints with path params
        if "get" in methods:
            resp = client.get(path)
            assert resp.status_code in (200, 204, 401, 403, 422), f"{path} -> {resp.status_code} {resp.text}"
            checked += 1

    assert checked > 0, "No collection GET endpoints were exercised"


def test_crud_cycle_districts_if_present(client):
    """
    If /districts endpoints exist and allow POST without full auth, do a tiny CRUD cycle.
    If POST is blocked by auth, we still consider the smoke test OK as long as it returns 401/403.
    """
    # Check route existence
    r = client.get("/openapi.json")
    spec = r.json()
    if "/districts" not in spec.get("paths", {}):
        return  # skip

    # CREATE
    payload = {"name": "Smoke District"}
    resp = client.post("/districts", json=payload)
    if resp.status_code in (401, 403):
        # Auth enforced; acceptable for smoke
        return
    assert resp.status_code in (200, 201), f"POST /districts failed: {resp.status_code} {resp.text}"
    created = resp.json()
    created_id = created.get("id")
    assert created_id, "Created district missing id"

    # LIST
    resp = client.get("/districts")
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)

    # GET by id (if route exposed)
    path_by_id = f"/districts/{created_id}"
    if path_by_id in spec["paths"]:
        resp = client.get(path_by_id)
        assert resp.status_code == 200
        assert resp.json().get("id") == created_id

    # UPDATE (PATCH or PUT) if available
    if "patch" in spec["paths"].get("/districts", {}):
        resp = client.patch("/districts", json={"id": created_id, "name": "Smoke District v2"})
        assert resp.status_code in (200, 204)
    elif "put" in spec["paths"].get("/districts", {}):
        resp = client.put("/districts", json={"id": created_id, "name": "Smoke District v2"})
        assert resp.status_code in (200, 204)

    # DELETE if available
    if "delete" in spec["paths"].get("/districts", {}):
        resp = client.delete("/districts", json={"id": created_id})
        assert resp.status_code in (200, 204)
    elif f"/districts/{created_id}" in spec["paths"] and "delete" in spec["paths"][f"/districts/{created_id}"]:
        resp = client.delete(f"/districts/{created_id}")
        assert resp.status_code in (200, 204)
