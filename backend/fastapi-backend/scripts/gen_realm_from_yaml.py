#!/usr/bin/env python3
import json, sys, pathlib
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "role-rules.yaml"
TEMPLATE_JSON = ROOT / "keycloak" / "realm-import.template.json"
OUTPUT_JSON = ROOT / "keycloak" / "real-export.json"

def _find_realm_role(roles_list, name):
    for r in roles_list:
        if r.get("name") == name:
            return r
    return None

def _find_client(clients, client_id):
    for c in clients:
        if c.get("clientId") == client_id:
            return c
    return None

def main():
    with YAML_PATH.open() as f:
        cfg = yaml.safe_load(f)

    with TEMPLATE_JSON.open() as f:
        realm = json.load(f)

    # 1) realm name
    realm["realm"] = cfg.get("realm", realm.get("realm", "myrealm"))

    # 2) realm roles
    realm_roles_cfg = cfg.get("realm_roles", {})
    realm.setdefault("roles", {}).setdefault("realm", [])
    realm_roles = realm["roles"]["realm"]

    # ensure each role exists with at least a description
    for key, role_name in realm_roles_cfg.items():
        existing = _find_realm_role(realm_roles, role_name)
        if not existing:
            realm_roles.append({"name": role_name, "description": f"{key} role from YAML"})

    # 3) client roles
    clients_cfg = cfg.get("clients", {})
    realm.setdefault("roles", {}).setdefault("client", {})
    realm_client_roles = realm["roles"]["client"]

    # clients list
    realm.setdefault("clients", [])
    for client_id, cdef in clients_cfg.items():
        roles = cdef.get("roles", [])
        # ensure client exists
        client = _find_client(realm["clients"], client_id)
        if not client:
            client = {
                "clientId": client_id,
                "name": client_id,
                "publicClient": True,
                "standardFlowEnabled": True,
                "directAccessGrantsEnabled": False,
                "serviceAccountsEnabled": False,
                "redirectUris": ["http://localhost:8000/*", "http://localhost:8000/docs/*"],
                "webOrigins": ["http://localhost:8000"],
                "attributes": {"pkce.code.challenge.method": "S256"},
                "defaultClientScopes": ["roles", "profile", "email", "web-origins"],
            }
            realm["clients"].append(client)

        # ensure roles object exists for client
        realm_client_roles.setdefault(client_id, [])
        existing_names = {r["name"] for r in realm_client_roles[client_id]}
        for rname in roles:
            if rname not in existing_names:
                realm_client_roles[client_id].append({"name": rname, "description": f"{client_id} role from YAML"})

    # 4) ensure a default group that contains the realm admin (optional)
    admin_role = realm_roles_cfg.get("admin")
    if admin_role:
        realm.setdefault("groups", [])
        if not any(g.get("name") == "admins" for g in realm["groups"]):
            realm["groups"].append({"name": "admins", "realmRoles": [admin_role]})
        else:
            for g in realm["groups"]:
                if g["name"] == "admins" and admin_role not in (g.get("realmRoles") or []):
                    g.setdefault("realmRoles", []).append(admin_role)

    # write final file Keycloak will import
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w") as f:
        json.dump(realm, f, indent=2)
    print(f"Wrote {OUTPUT_JSON}")

if __name__ == "__main__":
    sys.exit(main())
