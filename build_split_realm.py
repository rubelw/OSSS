#!/usr/bin/env python3
"""
Split/reorder a Keycloak realm export into:
  1) <realm>-realm.json               (realm core: NO users/roles/clients/groups/defaultRoles)
  2) <realm>-roles.json               (roles.realm + roles.client)
  3) <realm>-clients.json             (clients list)
  4) <realm>-groups.json              (group tree WITHOUT any role grants)
  5) <realm>-group-role-mappings.json (declarative grants for groups → realm/client roles)
  6) Users files (NOW WRAPPED as {"realm": <realm>, "users": [...]})

Usage:
  python build_split_realm.py \
      --in OSSS-realm.json \
      --realm-out OSSS-realm.json \
      --roles-out OSSS-roles.json \
      --clients-out OSSS-clients.json \
      --groups-out OSSS-groups.json \
      --group-maps-out OSSS-group-role-mappings.json \
      [--users-out OSSS-users.json | --users-chunk-size 500]
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

GROUP_CORE_KEYS_KEEP = {
    "id", "name", "path", "parentId", "attributes",
    "realmRoles", "clientRoles", "clientRoleMappings",
    "subGroups", "access"
}

def _load_realm(export_path: Path) -> Dict[str, Any]:
    data = json.loads(export_path.read_text(encoding="utf-8"))
    realm = data[0] if isinstance(data, list) else data
    if not isinstance(realm, dict) or "realm" not in realm:
        raise ValueError("Input does not look like a Keycloak realm export.")
    return realm


def _chunk_users(users: List[Dict[str, Any]], chunk_size: int) -> List[List[Dict[str, Any]]]:
    if not users:
        return []
    if chunk_size and chunk_size > 0:
        return [users[i:i + chunk_size] for i in range(0, len(users), chunk_size)]
    return [users]


def _strip_keys(d: Dict[str, Any], rm: List[str]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if k not in rm}


def _collect_group_role_mappings(group: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    name = group.get("name")
    path = group.get("path")
    grants: Dict[str, Any] = {"name": name}
    if path:
        grants["path"] = path

    # Gather realm role grants if present
    realm_roles = group.get("realmRoles") or []
    if realm_roles:
        grants["realmRoles"] = list(realm_roles)

    # Client roles (two possible shapes)
    client_roles_out: Dict[str, List[str]] = {}

    # Form A
    client_roles_map = group.get("clientRoles") or {}
    for client_id, role_list in client_roles_map.items():
        if role_list:
            client_roles_out.setdefault(client_id, []).extend(role_list)

    # Form B
    crm = group.get("clientRoleMappings") or []
    for entry in crm:
        cid = entry.get("client")
        roles = entry.get("roles") or []
        names = [r.get("name") for r in roles if isinstance(r, dict) and r.get("name")]
        if cid and names:
            client_roles_out.setdefault(cid, []).extend(names)

    if client_roles_out:
        grants["clientRoles"] = {cid: sorted(set(rl)) for cid, rl in client_roles_out.items()}

    # Build group node WITHOUT grants, recurse into subGroups
    stripped = {k: v for k, v in group.items() if k in GROUP_CORE_KEYS_KEEP}
    stripped.pop("realmRoles", None)
    stripped.pop("clientRoles", None)
    stripped.pop("clientRoleMappings", None)

    sub = group.get("subGroups") or []
    new_sub = []
    sub_grants_all: List[Dict[str, Any]] = []
    for sg in sub:
        sg_no, sg_grants = _collect_group_role_mappings(sg)
        new_sub.append(sg_no)
        sub_grants_all.extend(sg_grants)
    if new_sub:
        stripped["subGroups"] = new_sub

    all_grants: List[Dict[str, Any]] = []
    if "realmRoles" in grants or "clientRoles" in grants:
        all_grants.append(grants)
    all_grants.extend(sub_grants_all)
    return stripped, all_grants


def _collect_all_group_grants(groups: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    out_groups: List[Dict[str, Any]] = []
    grants_agg: List[Dict[str, Any]] = []
    for g in groups:
        g_no, g_grants = _collect_group_role_mappings(g)
        out_groups.append(g_no)
        grants_agg.extend(g_grants)
    return out_groups, grants_agg


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Reorder a Keycloak realm export into realm, roles, clients, groups, "
            "group role mappings, and users (wrapped with realm)."
        )
    )
    ap.add_argument("--in", dest="inp", required=True, help="Path to realm export JSON (realm-export.json)")
    ap.add_argument("--realm-out", dest="realm_out", help="Output path for <realm>-realm.json")
    ap.add_argument("--roles-out", dest="roles_out", help="Output path for <realm>-roles.json")
    ap.add_argument("--clients-out", dest="clients_out", help="Output path for <realm>-clients.json")
    ap.add_argument("--groups-out", dest="groups_out", help="Output path for <realm>-groups.json")
    ap.add_argument("--group-maps-out", dest="group_maps_out", help="Output path for <realm>-group-role-mappings.json")
    ap.add_argument(
        "--users-out",
        dest="users_out",
        help="Optional single users file (WRAPPED as {\"realm\": <realm>, \"users\": [...]})"
    )
    ap.add_argument(
        "--users-chunk-size",
        dest="chunk_size",
        type=int,
        default=0,
        help="Optional users chunk size; default 0 = single chunk file if users exist"
    )

    ap.add_argument(
        "--clients-keep-builtins", action="store_true",
        help="Keep built-in realm clients (account, realm-management, etc.)"
    )
    ap.add_argument(
        "--clients-builtins",
        default="admin-cli,account,account-console,broker,realm-management,security-admin-console",
        help="Comma-separated list of clientIds considered built-in"
    )
    args = ap.parse_args()

    in_path = Path(args.inp)
    if not in_path.exists():
        raise SystemExit(f"Input file not found: {in_path}")

    realm = _load_realm(in_path)
    realm_name: str = realm.get("realm")
    users: List[Dict[str, Any]] = list(realm.get("users") or [])
    roles: Dict[str, Any] = dict(realm.get("roles") or {})
    clients: List[Dict[str, Any]] = list(realm.get("clients") or [])
    groups: List[Dict[str, Any]] = list(realm.get("groups") or [])

    # 1) realm core (strip references)
    rm_keys = ["users", "roles", "clients", "groups", "defaultRoles", "defaultRole"]
    realm_core = _strip_keys(realm, rm_keys)

    # 2) roles payload (wrapped under "roles" for import)
    roles_payload: Dict[str, Any] = {}
    if roles:
        rp: Dict[str, Any] = {}

        # Filter realm roles to drop Keycloak built-ins so --override=false is safe
        # Built-ins: default-roles-*, offline_access, uma_authorization
        realm_roles = roles.get("realm") or []
        if realm_roles:
            filtered = []
            for r in realm_roles:
                if not isinstance(r, dict):
                    continue
                name = r.get("name") or ""
                if name.startswith("default-roles-") or name in ("offline_access", "uma_authorization"):
                    continue
                filtered.append(r)
            if filtered:
                rp["realm"] = filtered

        # Keep client roles as-is
        if roles.get("client"):
            rp["client"] = roles["client"]

        if rp:
            roles_payload = rp

    # 3) clients payload (array)
    clients_payload = clients if clients else []

    # Drop built-in clients unless explicitly kept
    if clients_payload and not args.clients_keep_builtins:
        _builtins = {s.strip() for s in args.clients_builtins.split(",") if s.strip()}
        clients_payload = [c for c in clients_payload if c.get("clientId") not in _builtins]

    # 4) groups + 5) group role mappings
    groups_output: List[Dict[str, Any]] = []
    group_maps_output: Dict[str, Any] = {}
    if groups:
        groups_no_grants, grants = _collect_all_group_grants(groups)
        groups_output = groups_no_grants
        if grants:
            group_maps_output = {
                "realm": realm_name,
                "groupRoleMappings": grants,
            }

    # 6) users (NOW WRAPPED with realm)
    written_user_files: List[str] = []
    if users:
        def _wrap(chunk: List[Dict[str, Any]]) -> Dict[str, Any]:
            return {"realm": realm_name, "users": chunk}

        if args.users_out:
            users_out = Path(args.users_out)
            users_out.write_text(json.dumps(_wrap(users), indent=2), encoding="utf-8")
            written_user_files.append(str(users_out))
        else:
            chunks = _chunk_users(users, args.chunk_size)
            for idx, chunk in enumerate(chunks):
                upath = in_path.with_name(f"{realm_name}-users-{idx}.json")
                upath.write_text(json.dumps(_wrap(chunk), indent=2), encoding="utf-8")
                written_user_files.append(str(upath))

    # Resolve output paths (define ALL before writing)
    realm_out = Path(args.realm_out) if args.realm_out else in_path.with_name(f"{realm_name}-realm.json")
    roles_out = Path(args.roles_out) if args.roles_out else in_path.with_name(f"{realm_name}-roles.json")
    clients_out = Path(args.clients_out) if args.clients_out else in_path.with_name(f"{realm_name}-clients.json")
    groups_out = Path(args.groups_out) if args.groups_out else in_path.with_name(f"{realm_name}-groups.json")
    group_maps_out = Path(args.group_maps_out) if args.group_maps_out else in_path.with_name(f"{realm_name}-group-role-mappings.json")

    # Write outputs IN ORDER
    realm_out.write_text(json.dumps(realm_core, indent=2), encoding="utf-8")

    if roles_payload:
        roles_wrapped = {"realm": realm_name, "roles": roles_payload}
        roles_out.write_text(json.dumps(roles_wrapped, indent=2), encoding="utf-8")

    if clients_payload:
        clients_wrapped = {"realm": realm_name, "clients": clients_payload}
        clients_out.write_text(json.dumps(clients_wrapped, indent=2), encoding="utf-8")

    if groups_output:
        groups_wrapped = {"realm": realm_name, "groups": groups_output}
        groups_out.write_text(json.dumps(groups_wrapped, indent=2), encoding="utf-8")

    if group_maps_output:
        group_maps_out.write_text(json.dumps(group_maps_output, indent=2), encoding="utf-8")

    summary = {
        "realm": realm_name,
        "realm_out": str(realm_out),
        "roles_out": str(roles_out) if roles_payload else None,
        "clients_out": str(clients_out) if clients_payload else None,
        "groups_out": str(groups_out) if groups_output else None,
        "group_maps_out": str(group_maps_out) if group_maps_output else None,
        "user_count": len(users),
        "users_files": written_user_files,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()