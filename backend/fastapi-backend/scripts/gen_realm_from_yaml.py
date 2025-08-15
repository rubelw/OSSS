#!/usr/bin/env python3
import json, sys, pathlib
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "role-rules.yaml"
TEMPLATE_JSON = ROOT / "keycloak" / "templates" / "realm-import.template.json"  # now in templates/
OUTPUT_JSON = ROOT / "keycloak" / "import" / "realm-export.json"               # now in import/

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

def _dedupe_roles_by_name(roles_list):
    """Return a list of roles deduped by name, keeping the first occurrence."""
    seen = set()
    out = []
    for r in roles_list:
        name = r.get("name")
        if name and name not in seen:
            seen.add(name)
            out.append(r)
    return out

def main():
    with YAML_PATH.open() as f:
        cfg = yaml.safe_load(f) or {}

    with TEMPLATE_JSON.open() as f:
        realm = json.load(f)

    # 1) realm name
    realm["realm"] = cfg.get("realm", realm.get("realm", "myrealm"))

    # 2) realm roles
    realm_roles_cfg = cfg.get("realm_roles", {}) or {}
    realm.setdefault("roles", {}).setdefault("realm", [])
    realm_roles = realm["roles"]["realm"]

    # ensure each role exists with at least a description
    for key, role_name in realm_roles_cfg.items():
        if not _find_realm_role(realm_roles, role_name):
            realm_roles.append({"name": role_name, "description": f"{key} role from YAML"})

    # de-duplicate realm roles by name
    realm["roles"]["realm"] = _dedupe_roles_by_name(realm_roles)

    # 3) client roles
    clients_cfg = cfg.get("clients", {}) or {}
    realm.setdefault("roles", {}).setdefault("client", {})
    realm_client_roles = realm["roles"]["client"]

    # clients list (ensure exists)
    realm.setdefault("clients", [])

    for client_id, cdef in clients_cfg.items():
        roles = (cdef or {}).get("roles", []) or []

        # ensure client exists
        client = _find_client(realm["clients"], client_id)
        if not client:
            client = {
                "clientId": client_id,
                "name": client_id,
                "protocol": "openid-connect",  # ensure protocol
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
        else:
            # ensure protocol on pre-existing client
            client.setdefault("protocol", "openid-connect")

        # ensure roles object exists for this client
        realm_client_roles.setdefault(client_id, [])
        existing_names = {r.get("name") for r in realm_client_roles[client_id] if r.get("name")}
        for rname in roles:
            if rname not in existing_names:
                realm_client_roles[client_id].append(
                    {"name": rname, "description": f"{client_id} role from YAML"}
                )
                existing_names.add(rname)

        # de-duplicate client roles (defensive, in case template had dupes)
        realm_client_roles[client_id] = _dedupe_roles_by_name(realm_client_roles[client_id])

    # 4) ensure a default group that contains the realm admin (optional)
    admin_role = realm_roles_cfg.get("admin")
    if admin_role:
        realm.setdefault("groups", [])
        grp = next((g for g in realm["groups"] if g.get("name") == "admins"), None)
        if not grp:
            realm["groups"].append({"name": "admins", "realmRoles": [admin_role]})
        else:
            grp.setdefault("realmRoles", [])
            if admin_role not in grp["realmRoles"]:
                grp["realmRoles"].append(admin_role)

    # write final file Keycloak will import
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w") as f:
        json.dump(realm, f, indent=2)
    print(f"Wrote {OUTPUT_JSON}")

if __name__ == "__main__":
    sys.exit(main())
