#!/usr/bin/env python3
"""
build_realm.py — debug-friendly, permissive

What's inside:
- Detailed debug logging (--debug / --trace flags; or KC_DEBUG=1)
- DEFAULT_FLOW_BINDINGS auto-applied to new clients unless overridden
- add_realm_role is permissive (accepts composites, clientRole, containerId, etc.)
- add_client_scope accepts both protocol_mappers (snake) and protocolMappers (camel)
- add_builtin_oidc_scopes() provided (you asked for this)
"""
from __future__ import annotations

import json
import logging
import os
import uuid
import importlib
import pkgutil
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable
import sqlalchemy as sa
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ConfigDict, model_validator

# Remove // line comments and /* block */ comments
_COMMENT_BLOCK_RE = re.compile(r"/\*.*?\*/", re.S)
_COMMENT_LINE_RE = re.compile(r"//.*?$", re.M)

SESSION_TTLS = {
    "ssoSessionIdleTimeout": 1800,       # 30 minutes
    "ssoSessionMaxLifespan": 36000,      # 10 hours
    "offlineSessionIdleTimeout": 2592000 # 30 days
}

# Match: Table <name> [optional settings] { ... }
# <name> can be: unquoted, "double-quoted", `backticked`, or schema.name
_TABLE_RE = re.compile(
    r"""
    \bTable                           # keyword
    \s+
    (                                 # capture name token (with optional quotes)
        "(?P<dquoted>[^"]+)"          # "Name"
        |
        `(?P<bquoted>[^`]+)`          # `Name`
        |
        (?P<raw>[A-Za-z0-9_.]+)       # schema.name or plain
    )
    (?:\s+as\s+[A-Za-z0-9_."`]+)?     # optional 'as Alias'
    (?:\s*\[[^\]]*\])?                # optional [settings: ...]
    \s*\{                             # opening brace of table body
    """,
    re.X | re.I,
)


# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------

LOG = logging.getLogger("realm_builder")

def configure_logging(debug: bool = False, trace: bool = False) -> None:
    level = logging.DEBUG if (debug or os.getenv("KC_DEBUG") == "1") else logging.INFO
    if trace:
        logging.addLevelName(5, "TRACE")
        level = 5
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

# ---------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------

DEFAULT_FLOW_BINDINGS: Dict[str, str] = {
    # "browser": "browser", ...  # <-- REMOVE defaults for now
}
DEFAULT_AUTHENTICATION_FLOWS: List[Dict[str, Any]] = []  # keep empty
# ---------------------------------------------------------------------
# Utils
# ---------------------------------------------------------------------
def to_names_from_position(name: str) -> tuple[str, str]:
    """
    Turn a position name like 'position_board_chair' into ('Board', 'Chair').
    If it doesn't start with 'position_', it still tries to split on underscores.
    """
    base = name[len("position_"):] if str(name).startswith("position_") else str(name)
    parts = [p for p in base.split("_") if p]
    if not parts:
        return ("", "")
    if len(parts) == 1:
        return (parts[0].title(), "")
    return (" ".join(p.title() for p in parts[:-1]), parts[-1].title())

def _uuid() -> str:
    return str(uuid.uuid4())

def _dedupe(seq: List[Any]) -> List[Any]:
    seen: set = set()
    out: List[Any] = []
    for x in seq:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out

def _strip_quotes(name: str) -> str:
    # just in case a different bracket sneaks in
    if (name.startswith('"') and name.endswith('"')) or \
       (name.startswith('`') and name.endswith('`')) or \
       (name.startswith('[') and name.endswith(']')):
        return name[1:-1]
    return name

def _preprocess(text: str) -> str:
    text = _COMMENT_BLOCK_RE.sub("", text)
    text = _COMMENT_LINE_RE.sub("", text)
    return text

def iter_table_names(text: str) -> Iterable[str]:
    cleaned = _preprocess(text)
    for m in _TABLE_RE.finditer(cleaned):
        name = m.group("dquoted") or m.group("bquoted") or m.group("raw") or ""
        yield _strip_quotes(name).strip()


def read_dbml_file(path: str) -> str:
    """
    Reads a DBML file from disk and returns its contents as a string.

    Args:
        path: Path to the .dbml file.

    Returns:
        The text content of the DBML file.
    """
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"DBML file not found: {path}")

    with p.open("r", encoding="utf-8") as f:
        return f.read()

def import_all_models(root_pkg: str) -> None:
    """
    Import all modules under the given package so that all model classes register
    themselves on their SQLAlchemy Base.metadata.
    """
    pkg = importlib.import_module(root_pkg)
    pkg_path = getattr(pkg, "__path__", None)
    if not pkg_path:
        return

    prefix = pkg.__name__ + "."
    for modinfo in pkgutil.walk_packages(pkg_path, prefix=prefix):
        fullname = modinfo.name
        # Skip private or tests/migrations-like modules
        parts = fullname.split(".")
        if any(p.startswith("_") for p in parts):
            continue
        if any(p in {"tests", "migrations"} for p in parts):
            continue

        try:
            importlib.import_module(fullname)
            logging.getLogger(__name__).debug("Imported %s", fullname)
        except Exception as exc:
            logging.getLogger(__name__).warning("Skipping %s due to import error: %s", fullname, exc)


def _compile_type(coltype: sa.types.TypeEngine) -> str:
    """Map SQLAlchemy types to DBML-ish names. Fallback to str(coltype)."""
    t = coltype
    # Common types
    if isinstance(t, sa.String):
        if getattr(t, "length", None):
            return f"varchar({t.length})"
        return "text"
    if isinstance(t, sa.Text):
        return "text"
    if isinstance(t, sa.Integer):
        return "int"
    if isinstance(t, sa.BigInteger):
        return "bigint"
    if isinstance(t, sa.SmallInteger):
        return "smallint"
    if isinstance(t, sa.Numeric):
        if getattr(t, "precision", None) is not None and getattr(t, "scale", None) is not None:
            return f"numeric({t.precision},{t.scale})"
        return "numeric"
    if isinstance(t, sa.Float):
        return "float"
    if isinstance(t, sa.Boolean):
        return "boolean"
    if isinstance(t, sa.Date):
        return "date"
    if isinstance(t, sa.DateTime) or isinstance(t, sa.types.TIMESTAMP):
        return "timestamp"
    if isinstance(t, sa.types.UUID):
        return "uuid"
    # Dialect-specific or custom
    try:
        from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, JSON, INET
        if isinstance(t, PGUUID):
            return "uuid"
        if isinstance(t, JSONB):
            return "jsonb"
        if isinstance(t, JSON):
            return "json"
        if isinstance(t, INET):
            return "inet"
    except Exception:
        pass
    if isinstance(t, sa.JSON):
        return "json"
    # Fallback
    return str(t)


def _default_to_str(col: sa.Column) -> Optional[str]:
    # Column default (client side)
    if col.default is not None:
        try:
            if col.default.is_scalar:
                return repr(col.default.arg)
        except Exception:
            pass
    # Server default
    if col.server_default is not None:
        try:
            # Often a SQL ClauseElement/TextClause
            return str(getattr(col.server_default.arg, "text", col.server_default.arg))
        except Exception:
            return str(col.server_default)
    return None


def emit_table_dbml(table: sa.Table) -> str:
    """Emit a DBML block for a single Table."""
    name = table.name
    schema = table.schema
    fq_name = f"{schema}.{name}" if schema else name

    lines = [f"Table {fq_name} {{"]

    # Columns
    for col in table.columns:
        parts = [f"  {col.name} {_compile_type(col.type)}"]
        attrs = []
        if col.primary_key:
            attrs.append("pk")
        if not col.nullable:
            attrs.append("not null")
        if col.unique:
            attrs.append("unique")
        dflt = _default_to_str(col)
        if dflt is not None:
            # escape braces/quotes lightly
            dflt_clean = str(dflt).replace("{", "\{").replace("}", "\}")
            attrs.append(f'default: "{dflt_clean}"')
        if getattr(col, "autoincrement", False):
            attrs.append("increment")
        if attrs:
            parts.append(f"[{', '.join(attrs)}]")
        lines.append(" ".join(parts))

    # Indexes (simple)
    if table.indexes:
        lines.append("")
        lines.append("  Indexes {")
        for idx in sorted(table.indexes, key=lambda i: i.name or ""):
            cols = ", ".join(getattr(c, "name", str(c)) for c in idx.expressions)
            flags = []
            if idx.unique:
                flags.append("unique")
            idx_name = f' name: "{idx.name}"' if idx.name else ""
            flag_str = f" [{', '.join(flags)}{(',' if flags and idx_name else '')}{idx_name.strip()}]" if (flags or idx_name) else ""
            lines.append(f"    ({cols}){flag_str}")
        lines.append("  }")

    # Unique constraints (composite)
    uniques = [
        c for c in table.constraints
        if isinstance(c, sa.UniqueConstraint) and len(c.columns) > 1
    ]
    if uniques:
        lines.append("")
        lines.append("  Indexes {")
        for uc in uniques:
            cols = ", ".join(col.name for col in uc.columns)
            uc_name = f' name: "{uc.name}"' if uc.name else ""
            lines.append(f"    ({cols}) [unique{(',' if uc_name else '')}{uc_name}]")
        lines.append("  }")

    lines.append("}")
    return "\n".join(lines)


def emit_refs_dbml(metadata: sa.MetaData) -> str:
    """Emit DBML Ref lines for all foreign keys in metadata."""
    out = []
    for table in metadata.tables.values():
        for fk in table.foreign_keys:
            src = f"{table.schema + '.' if table.schema else ''}{table.name}.{fk.parent.name}"
            reft = fk.column.table
            tgt = f"{reft.schema + '.' if reft.schema else ''}{reft.name}.{fk.column.name}"
            opts = []
            ondelete = getattr(fk.constraint, "ondelete", None)
            onupdate = getattr(fk.constraint, "onupdate", None)
            if ondelete:
                opts.append(f"delete: {ondelete}")
            if onupdate:
                opts.append(f"update: {onupdate}")
            opt_str = f" [{', '.join(opts)}]" if opts else ""
            out.append(f"Ref: {src} > {tgt}{opt_str}")
    return "\n".join(out)

def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)

def _normalize_attrs(attrs: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for k, v in (attrs or {}).items():
        if v is None:
            continue
        if isinstance(v, list):
            out[k] = [str(x) for x in v if x is not None]
        else:
            out[k] = [str(v)]
    return out

# ---------------------------------------------------------------------
# Models (subset of Keycloak export schema)
# ---------------------------------------------------------------------

class ProtocolMapperRepresentation(BaseModel):
    name: str
    protocol: str = "openid-connect"
    protocolMapper: str
    consentRequired: bool = False
    consentText: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


class ClientScopeRepresentation(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    protocol: str = "openid-connect"
    attributes: Dict[str, Any] = Field(default_factory=dict)
    protocolMappers: List[ProtocolMapperRepresentation] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class RoleRepresentation(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    composite: bool = False
    clientRole: bool = False
    containerId: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    composites: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def _coerce_attribute_lists(self):
        if self.attributes:
            self.attributes = {
                k: v if isinstance(v, list) else [str(v)]
                for k, v in self.attributes.items()
            }
        return self


class RolesRepresentation(BaseModel):
    realm: List[RoleRepresentation] = Field(default_factory=list)
    client: Dict[str, List[RoleRepresentation]] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


class GroupRepresentation(BaseModel):
    id: Optional[str] = None
    name: str
    path: Optional[str] = None
    attributes: Optional[Dict[str, List[str]]] = None
    subGroups: Optional[List["GroupRepresentation"]] = None
    realmRoles: Optional[List[str]] = None
    clientRoles: Optional[Dict[str, List[str]]] = None

    model_config = ConfigDict(extra="ignore")

class CredentialRepresentation(BaseModel):
    type: str = "password"
    value: str
    temporary: bool = False
    model_config = ConfigDict(extra="ignore")

class UserRepresentation(BaseModel):
    id: Optional[str] = None
    username: str
    email: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    enabled: bool = True
    emailVerified: bool = False
    attributes: Dict[str, Any] = Field(default_factory=dict)
    realmRoles: List[str] = Field(default_factory=list)
    clientRoles: Dict[str, List[str]] = Field(default_factory=dict)
    requiredActions: List[str] = Field(default_factory=list)
    groups: List[str] = Field(default_factory=list)
    credentials: List[CredentialRepresentation] = Field(default_factory=list)


    # Extra optional exports commonly present
    totp: Optional[bool] = None
    disableableCredentialTypes: Optional[List[str]] = None
    notBefore: Optional[int] = None
    createdTimestamp: Optional[int] = None
    serviceAccountClientId: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class ClientRepresentation(BaseModel):
    id: Optional[str] = None
    clientId: str
    name: Optional[str] = None

    rootUrl: Optional[str] = None
    baseUrl: Optional[str] = None
    adminUrl: Optional[str] = None
    secret: Optional[str] = None

    publicClient: bool = False
    bearerOnly: bool = False
    directAccessGrantsEnabled: bool = False
    serviceAccountsEnabled: bool = False
    standardFlowEnabled: bool = True
    implicitFlowEnabled: bool = False
    frontchannelLogout: bool = False
    consentRequired: bool = False

    redirectUris: List[str] = Field(default_factory=list)
    webOrigins: List[str] = Field(default_factory=list)

    notBefore: int = 0
    alwaysDisplayInConsole: bool = False
    surrogateAuthRequired: bool = False
    nodeReRegistrationTimeout: int = 0
    protocol: str = "openid-connect"
    attributes: Dict[str, Any] = Field(default_factory=dict)
    authenticationFlowBindingOverrides: Dict[str, Any] = Field(default_factory=dict)

    protocolMappers: Optional[List[ProtocolMapperRepresentation]] = None
    defaultClientScopes: Optional[List[str]] = None
    optionalClientScopes: Optional[List[str]] = None

    clientAuthenticatorType: Optional[str] = None
    fullScopeAllowed: Optional[bool] = None
    enabled: Optional[bool] = True

    authorizationServicesEnabled: Optional[bool] = None
    authorizationSettings: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="ignore")


class RealmRepresentation(BaseModel):
    id: Optional[str] = None
    realm: str
    enabled: bool = True

    roles: RolesRepresentation = Field(default_factory=RolesRepresentation)
    users: List[UserRepresentation] = Field(default_factory=list)
    clients: List[ClientRepresentation] = Field(default_factory=list)
    groups: List[GroupRepresentation] = Field(default_factory=list)

    clientScopes: List[ClientScopeRepresentation] = Field(default_factory=list)

    # flows
    authenticationFlows: List[Dict[str, Any]] = Field(default_factory=lambda: list(DEFAULT_AUTHENTICATION_FLOWS))

    # Built-in flow bindings
    browserFlow: str = "browser"
    registrationFlow: str = "registration"
    directGrantFlow: str = "direct grant"
    resetCredentialsFlow: str = "reset credentials"
    clientAuthenticationFlow: str = "clients"
    dockerAuthenticationFlow: str = "docker auth"

    model_config = ConfigDict(extra="ignore")

# ---------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------

class RealmBuilder:
    def __init__(self, name: str, enabled: bool = True):
        self.realm = RealmRepresentation(realm=name, enabled=enabled)
        LOG.debug("Initialized RealmBuilder for realm=%s enabled=%s", name, enabled)

    def _find_top_group(self, name: str):
        for g in (self.realm.groups or []):
            if g.name == name:
                return g
        return None

    def _find_child_group(self, parent, name: str):
        for g in (getattr(parent, "subGroups", None) or []):
            if g.name == name:
                return g
        return None

    def ensure_group_path(self, path: str):
        """
        Ensure a group path like '/a/b/c' exists in self.realm.groups.
        Creates any missing groups on the way and returns the deepest group.
        """
        if not path or path == "/":
            raise ValueError("Group path must look like '/segment[/segment]*'")

        parts = [p for p in path.split("/") if p]
        # Top-level
        current = self._find_top_group(parts[0])
        if current is None:
            current = GroupRepresentation(id=_uuid(), name=parts[0], subGroups=[])
            self.realm.groups.append(current)

        # Children
        for name in parts[1:]:
            child = self._find_child_group(current, name)
            if child is None:
                child = GroupRepresentation(id=_uuid(), name=name, subGroups=[])
                if current.subGroups is None:
                    current.subGroups = []
                current.subGroups.append(child)
            current = child

        return current

    def _finalize_for_export(self) -> Dict[str, Any]:
        data = self.realm.model_dump(exclude_none=True)  # make sure exclude_none=True is used
        if not data.get("authenticationFlows"):
            # Drop realm-level bindings so KC uses built-ins
            for k in ("browserFlow", "registrationFlow", "directGrantFlow",
                      "resetCredentialsFlow", "clientAuthenticationFlow", "dockerAuthenticationFlow"):
                data.pop(k, None)
            # Drop client-level overrides
            for c in data.get("clients", []):
                c.pop("authenticationFlowBindingOverrides", None)
        return data

    # --- roles ---
    def add_realm_role(
        self,
        name: str,
        description: Optional[str] = None,
        *,
        attributes: Optional[Dict[str, Any]] = None,
        composite: bool = False,
        client_role: bool = False,
        container_id: Optional[str] = None,
        composites: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> "RealmBuilder":
        # Accept KC-style aliases
        if "clientRole" in kwargs and kwargs["clientRole"] is not None:
            client_role = kwargs["clientRole"]
        if "containerId" in kwargs and kwargs["containerId"] is not None:
            container_id = kwargs["containerId"]
        if composites is None and "composites" in kwargs:
            composites = kwargs["composites"]

        LOG.debug(
            "add_realm_role(name=%s, composite=%s, client_role=%s, container_id=%s, composites_keys=%s)",
            name, composite, client_role, container_id, list((composites or {}).keys())
        )
        self.realm.roles.realm.append(
            RoleRepresentation(
                name=name,
                description=description,
                composite=composite,
                clientRole=client_role,
                containerId=container_id,
                attributes=attributes or {},
                composites=composites,
            )
        )
        return self

    def ensure_roles_scope_with_mappers(self) -> "RealmBuilder":
        # Build the two mappers Keycloak’s built-in "roles" scope normally has
        realm_roles_pm = ProtocolMapperRepresentation(
            name="realm roles",
            protocolMapper="oidc-usermodel-realm-role-mapper",
            config={
                "multivalued": "true",
                "access.token.claim": "true",
                "id.token.claim": "true",
                "userinfo.token.claim": "true",
                "claim.name": "realm_access.roles",
            },
        )
        client_roles_pm = ProtocolMapperRepresentation(
            name="client roles",
            protocolMapper="oidc-usermodel-client-role-mapper",
            config={
                "multivalued": "true",
                "access.token.claim": "true",
                "id.token.claim": "true",
                "userinfo.token.claim": "true",
                # This claim name produces resource_access.<clientId>.roles
                "claim.name": "resource_access.${client_id}.roles",
            },
        )

        # If "roles" exists, make sure it has mappers; otherwise create it.
        for cs in self.realm.clientScopes:
            if cs.name == "roles":
                if not cs.protocolMappers or len(cs.protocolMappers) == 0:
                    cs.protocolMappers = [realm_roles_pm, client_roles_pm]
                return self

        # Not found: create it
        return self.add_client_scope(
            name="roles",
            protocol="openid-connect",
            protocol_mappers=[realm_roles_pm, client_roles_pm],
        )


    def ensure_realm_role(self, name: str, description: Optional[str] = None, **kwargs) -> "RealmBuilder":
        for r in self.realm.roles.realm:
            if r.name == name:
                return self
        return self.add_realm_role(name, description, **kwargs)

    def add_client_role(self, client_id: str, name: str, description: Optional[str] = None, **kwargs) -> "RealmBuilder":
        role = RoleRepresentation(name=name, description=description, clientRole=True, containerId=client_id, **kwargs)

        self.realm.roles.client.setdefault(client_id, []).append(role)
        return self

    # --- clients ---
    def add_client(self, client_id: str, **kwargs) -> "RealmBuilder":

        kw = dict(kwargs)

        # Map our override name to KC's field
        overrides = kw.pop("authentication_flow_binding_overrides", None)
        if overrides is None:
            overrides = dict(DEFAULT_FLOW_BINDINGS)

        # Normalize snake_case -> camelCase for common client fields
        keymap = {
            "root_url": "rootUrl",
            "base_url": "baseUrl",
            "admin_url": "adminUrl",
            "public_client": "publicClient",
            "bearer_only": "bearerOnly",
            "direct_access_grants_enabled": "directAccessGrantsEnabled",
            "service_accounts_enabled": "serviceAccountsEnabled",
            "standard_flow_enabled": "standardFlowEnabled",
            "implicit_flow_enabled": "implicitFlowEnabled",
            "frontchannel_logout": "frontchannelLogout",
            "redirect_uris": "redirectUris",
            "web_origins": "webOrigins",
            "default_client_scopes": "defaultClientScopes",
            "optional_client_scopes": "optionalClientScopes",
            "client_authenticator_type": "clientAuthenticatorType",
            "full_scope_allowed": "fullScopeAllowed",
            "authorization_services_enabled": "authorizationServicesEnabled",
            "authorization_settings": "authorizationSettings",
        }
        for snake, camel in keymap.items():
            if snake in kw and camel not in kw:
                kw[camel] = kw.pop(snake)

        # Ensure list types for redirectUris/webOrigins
        for list_key in ("redirectUris", "webOrigins"):
            if list_key in kw and kw[list_key] is not None and not isinstance(kw[list_key], list):
                kw[list_key] = [kw[list_key]]

        # Build client
        client = ClientRepresentation(
            id=kw.pop("id", None) or _uuid(),
            clientId=client_id,
            authenticationFlowBindingOverrides=overrides,
            **kw,
        )
        self.realm.clients.append(client)
        LOG.debug("Added client: %s (total=%d) redirectUris=%s webOrigins=%s",
                  client_id, len(self.realm.clients),
                  getattr(client, "redirectUris", None),
                  getattr(client, "webOrigins", None))
        return self

    # --- groups ---
    def add_groups_from_hierarchy(
            self,
            hierarchy: Mapping[str, Any],
            *,
            include_position_groups: bool = True,
            unit_attr_key: str = "kind",
            position_attr_key: str = "kind",
            role_client_id: Optional[str] = None,
            # role_mapper takes a permissions list and returns (realm_roles, client_roles_map)
            role_mapper: Optional[
                Callable[[List[str]], Tuple[List[str], Dict[str, List[str]]]]
            ] = None,
    ) -> "RealmBuilder":
        """
        Create Keycloak groups/sub-groups from an org hierarchy dict,
        and attach role mappings derived from a `permissions` list on each node.

        Structure excerpt:
        {
          "organization": "school_district",
          "hierarchy": [
            {
              "unit": "...",
              "permissions": ["role_or_perm_1", ...],   # optional
              "positions": [
                { "name":"...", "description":"...", "permissions": ["..."] }, ...
              ],
              "children": [ {...}, ... ]
            }
          ]
        }

        Role mapping behavior:
          - If `role_mapper` is provided, it's used to convert `permissions` to
            `(realm_roles, client_roles_map)`.
          - Else, if `role_client_id` is provided, each permission becomes a client
            role of the same name on that client.
          - Else, no role mappings are attached.
        """
        LOG.debug(
            "add_groups_from_hierarchy: start (include_position_groups=%s, unit_attr_key=%s, position_attr_key=%s, role_client_id=%s, role_mapper=%s)",
            include_position_groups, unit_attr_key, position_attr_key, role_client_id, bool(role_mapper)
        )

        def _dedupe_sorted(seq: List[str]) -> List[str]:
            out = sorted(set(filter(None, seq)))
            if out != list(seq):
                LOG.debug("  _dedupe_sorted: input_len=%d -> unique_len=%d", len(seq), len(out))
            return out

        def _default_role_mapper(perms: List[str]) -> Tuple[List[str], Dict[str, List[str]]]:
            # Default: map permissions directly to client roles on `role_client_id`
            if role_client_id:
                LOG.debug("  default_role_mapper: mapping %d perms to client '%s'", len(perms), role_client_id)
                return ([], {role_client_id: _dedupe_sorted(perms)})
            LOG.debug("  default_role_mapper: no role_client_id; no role mappings")
            return ([], {})  # no mappings if no client specified

        use_role_mapper = role_mapper or _default_role_mapper

        LOG.debug("Role mapper: "+str(use_role_mapper))

        group_count = 0
        position_count = 0

        def _seg(name: str) -> str:
            # Keep the display name intact (including spaces);
            # only strip surrounding whitespace and fall back to 'Group' if empty.
            s = str(name or "").strip()
            return s or "Group"

        def _to_path(segments: list[str]) -> str:
            # Build "/A/B/C" from a list of names; compress any accidental empty segs.
            cleaned = [s for s in map(_seg, segments) if s]
            return "/" + "/".join(cleaned) if cleaned else "/"


        def _ensure_client_roles(client_id: Optional[str], roles: List[str]) -> None:
            if not client_id or not roles:
                return
            # Ensure the roles bucket exists
            if client_id not in self.realm.roles.client:
                self.realm.roles.client[client_id] = []
            existing = {r.name for r in self.realm.roles.client[client_id]}
            created = 0
            for rname in roles:
                if rname not in existing:
                    self.add_client_role(client_id, rname, description=f"Auto-created from hierarchy for {client_id}")
                    existing.add(rname)
                    created += 1
            if created:
                LOG.debug("  created %d client roles on '%s': %s", created, client_id, roles)

        def build_group(node: Mapping[str, Any], parent_segments: list[str] | None = None) -> GroupRepresentation:
            nonlocal group_count, position_count
            if parent_segments is None:
                parent_segments = []

            unit_name = (node.get("unit") or node.get("name") or "Unit")
            unit_perms: List[str] = node.get("permissions") or []

            my_segments = [*parent_segments, unit_name]
            unit_path = _to_path(my_segments)

            LOG.debug(" build_group: unit='%s' path='%s' perms=%d children=%d positions=%d",
                      unit_name, unit_path, len(unit_perms),
                      len(node.get("children") or []),
                      len(node.get("positions") or []))

            # Compute role mappings for this unit (if any)
            realm_roles: List[str]
            client_roles: Dict[str, List[str]]
            realm_roles, client_roles = use_role_mapper(unit_perms)
            LOG.debug("  unit role mapping: realm_roles=%d, client_roles clients=%s",
                      len(realm_roles), list((client_roles or {}).keys()))

            # Tag a unit group with attributes so you can filter in Keycloak UI later
            unit_attrs: Dict[str, List[str]] = {unit_attr_key: ["unit"]}

            subgroups: List[GroupRepresentation] = []

            # Add each position as a subgroup under the unit (optional)
            if include_position_groups:
                for pos in node.get("positions", []) or []:
                    pos_name = pos.get("name", "position")
                    pos_desc = pos.get("description", "")
                    pos_perms: List[str] = pos.get("permissions") or []

                    pos_path = _to_path([*my_segments, pos_name])
                    LOG.debug("   position subgroup: name='%s' path='%s' perms=%d", pos_name, pos_path, len(pos_perms))

                    pos_realm_roles, pos_client_roles = use_role_mapper(pos_perms)
                    LOG.debug("    position role mapping: realm_roles=%d, client_roles clients=%s",
                              len(pos_realm_roles), list((pos_client_roles or {}).keys()))

                    subgroups.append(
                        GroupRepresentation(
                            name=_seg(pos_name),
                            path=pos_path,
                            attributes={
                                position_attr_key: ["position"],
                                "description": [pos_desc] if pos_desc else [],
                            },
                            subGroups=[],
                            realmRoles=_dedupe_sorted(pos_realm_roles) or None,
                            clientRoles={k: _dedupe_sorted(v) for k, v in (pos_client_roles or {}).items()} or None,
                        )
                    )
                    position_count += 1

            # Recurse into child units
            for child in node.get("children", []) or []:
                child_group = build_group(child, my_segments)
                # Defensive: ensure child's path reflects the full ancestry
                if not getattr(child_group, "path", None):
                    child_group.path = _to_path([*my_segments, getattr(child_group, "name", "Group")])
                subgroups.append(child_group)

            group_rep = GroupRepresentation(
                name=_seg(unit_name),
                path=unit_path,
                attributes=unit_attrs,
                subGroups=subgroups,
                realmRoles=_dedupe_sorted(realm_roles) or None,
                clientRoles={k: _dedupe_sorted(v) for k, v in (client_roles or {}).items()} or None,
            )
            group_count += 1
            LOG.debug("  built group '%s' path='%s' with %d subgroups, realmRoles=%s, clientRoles=%s",
                      unit_name, unit_path,
                      len(subgroups),
                      (group_rep.realmRoles or []),
                      {k: len(v) for k, v in (group_rep.clientRoles or {}).items()} if group_rep.clientRoles else {})
            return group_rep


        roots = hierarchy.get("hierarchy", []) or []
        LOG.debug("add_groups_from_hierarchy: processing %d root node(s)", len(roots))

        # Top-level may contain multiple roots under "hierarchy"
        for root in roots:
            self.realm.groups.append(build_group(root))

            # Root is:
            # root [{'unit': 'board_of_education_governing_board', 'permissions': ['read:academic_terms', 'read:accommodations', 'read:activities', 'read:addresses', 'read:agenda_item_approvals', 'read:agenda_item_files', 'read:agenda_items', 'read:agenda_workflow_steps', 'read:agend

            LOG.debug("root %s", roots)



        LOG.debug("add_groups_from_hierarchy: done (groups_added=%d, position_groups_added=%d, total_top_level=%d)",
                  group_count, position_count, len(roots))

        return self

    # --- users ---
    def add_user(
            self,
            username: str,
            *,
            password: Optional[str] = None,  # <<< new
            temporary_password: bool = False,  # <<< new
            email: Optional[str] = None,
            first_name: Optional[str] = None,
            last_name: Optional[str] = None,
            enabled: bool = True,
            email_verified: bool = False,
            groups: Optional[List[str]] = None,
            attributes: Optional[Dict[str, Any]] = None,
            realm_roles: Optional[List[str]] = None,
            client_roles: Optional[Dict[str, List[str]]] = None,
            required_actions: Optional[List[str]] = None,
            totp: Optional[bool] = None,  # convenience; maps to CONFIGURE_TOTP
    ) -> "RealmBuilder":
        # start from caller-provided required actions
        req = list(required_actions or [])

        # map totp flag to Keycloak required action
        if totp is True and "CONFIGURE_TOTP" not in req:
            req.append("CONFIGURE_TOTP")
        elif totp is False and "CONFIGURE_TOTP" in req:
            req.remove("CONFIGURE_TOTP")

        credentials = (
            [{"type": "password", "value": password, "temporary": temporary_password}]
            if password is not None else []
        )

        # normalize attributes to list-of-strings and ensure CreatedAt exists
        norm_attrs = _normalize_attrs(attributes)
        if "CreatedAt" not in norm_attrs or not norm_attrs["CreatedAt"]:
            norm_attrs["CreatedAt"] = [datetime.now(timezone.utc).isoformat()]

        user = UserRepresentation(
            id=_uuid(),
            username=username,
            email=email,
            firstName=first_name,
            lastName=last_name,
            enabled=enabled,
            emailVerified=email_verified,
            groups=(groups or []),
            attributes=(attributes or {}),
            realmRoles=(realm_roles or []),
            clientRoles=(client_roles or {}),
            requiredActions=req,
            credentials=credentials,
            createdTimestamp=_now_ms(),

        )
        self.realm.users.append(user)
        LOG.debug(
            "Added user: %s (groups=%d, has_password=%s, temp=%s)",
            username, len(user.groups or []), bool(password), temporary_password
        )
        return self

    def add_users_from_rbac_positions(
            self,
            rbac: Mapping[str, Any],
            *,
            email_domain: str = "example.org",
            include_description_attribute: bool = True,
            password: Optional[str] = None,
            temporary_password: bool = False,
            password_field: str = "password",
    ) -> "RealmBuilder":
        """
        - Add a user for each position in 'positions'.
          * Group path: uses 'position_<slug>'
          * Username/email: use the base name WITHOUT 'position_'.
        - Also add one user per leaf unit (no children).
        """
        import re
        from typing import Dict

        def seg(name: str) -> str:
            s = str(name or "").strip()
            return s or "Group"

        def to_path(segments: list[str]) -> str:
            cleaned = [seg(s) for s in segments if s]
            return "/" + "/".join(cleaned) if cleaned else "/"

        def slugify(s: str) -> str:
            return re.sub(r"[^a-zA-Z0-9]+", "_", s.strip()).strip("_").lower() or "item"

        def split_names(s: str) -> tuple[str, str]:
            # Split human-readable first/last from a base string
            parts = [p for p in re.split(r"[^a-zA-Z0-9]+", s) if p]
            if not parts:
                return ("", "")
            if len(parts) == 1:
                return (parts[0].title(), "")
            return (" ".join(p.title() for p in parts[:-1]), parts[-1].title())

        added = 0

        def walk(node: Mapping[str, Any], parent_segments: list[str]) -> None:
            nonlocal added

            unit_name = seg(node.get("unit") or node.get("name"))
            my_segments = [*parent_segments, unit_name]

            # 1) Position-based users
            for pos in (node.get("positions") or []):
                raw_name = seg(pos.get("name"))  # e.g. "position_board_chair"


                # Groups use the full position name (with prefix) so paths match your group tree
                path = to_path([*my_segments, raw_name])  # "/board_of_education_governing_board/position_board_chair"
                self.ensure_group_path(path)

                # Usernames/emails drop the "position_" prefix
                uname_base = raw_name[len("position_"):]  # "board_chair"
                uname = raw_name  # keep underscores; Keycloak allows them
                LOG.debug("raw name: "+str(raw_name))
                first, last = to_names_from_position(raw_name)  # your existing helper
                if not last:
                    last = "LNU"
                email = f"{raw_name}@{email_domain}" if email_domain else None

                # choose password: explicit param > per-position field > None
                pw = password
                if pw is None and password_field and pos.get(password_field):
                    pw = str(pos[password_field])

                attrs: Dict[str, Any] = {}
                if include_description_attribute and pos.get("description"):
                    attrs["position_description"] = [pos["description"]]

                self.add_user(
                    username=uname,
                    email=email,
                    first_name=first or None,
                    last_name=last or None,
                    groups=[path],
                    attributes=attrs,
                    enabled=True,
                    email_verified=False,
                    password=pw,
                    temporary_password=temporary_password,
                )
                LOG.debug(
                    "add_users_from_rbac_positions: added POSITION user '%s' (group=%s, has_pw=%s, temp=%s)",
                    uname, path, bool(pw), temporary_password
                )
                added += 1

            # 2) LEAF-UNIT USER (unchanged)
            children = node.get("children") or []
            if not children:
                unit_path = to_path(my_segments)
                unit_slug = slugify(unit_name)
                uname = f"unit_{unit_slug}"
                first, last = split_names(unit_name)
                email = f"{uname}@{email_domain}" if email_domain else None

                pw = password
                if pw is None and password_field and node.get(password_field):
                    pw = str(node[password_field])

                attrs: Dict[str, Any] = {"unit_leaf": ["true"], "unit_name": [unit_name]}
                if include_description_attribute and node.get("description"):
                    attrs["unit_description"] = [node["description"]]

                self.add_user(
                    username=uname,
                    email=email,
                    first_name=first or None,
                    last_name=last or None,
                    groups=[unit_path],
                    attributes=attrs,
                    enabled=True,
                    email_verified=False,
                    password=pw,
                    temporary_password=temporary_password,
                )
                LOG.debug(
                    "add_users_from_rbac_positions: added LEAF-UNIT user '%s' (group=%s, has_pw=%s, temp=%s)",
                    uname, unit_path, bool(pw), temporary_password
                )
                added += 1

            for child in children:
                walk(child, my_segments)

        for root in (rbac.get("hierarchy") or []):
            walk(root, [])

        LOG.debug("add_users_from_rbac_positions: total users added=%d", added)
        return self

    def _get_client(self, client_id: str):
        for c in self.realm.clients or []:
            if getattr(c, "clientId", None) == client_id:
                return c
        raise KeyError(f"Client not found: {client_id}")

    def ensure_client_roles_scope(self, target_client_id: str, scope_name: str | None = None) -> "RealmBuilder":
        scope_name = scope_name or f"{target_client_id}-roles"
        pm = ProtocolMapperRepresentation(
            name=f"{target_client_id} client roles",
            protocolMapper="oidc-usermodel-client-role-mapper",
            config={
                "multivalued": "true",
                "access.token.claim": "true",
                "id.token.claim": "false",
                "userinfo.token.claim": "false",
                # Limit to a specific client’s roles:
                "usermodel.clientRoleMapping.clientId": target_client_id,
                "claim.name": f"resource_access.{target_client_id}.roles",
            },
        )

        # Upsert the scope
        for cs in self.realm.clientScopes:
            if cs.name == scope_name:
                if not cs.protocolMappers or len(cs.protocolMappers) == 0:
                    cs.protocolMappers = [pm]
                return self

        return self.add_client_scope(
            name=scope_name, protocol="openid-connect", protocol_mappers=[pm]
        )


    def ensure_client_default_scopes(
            self,
            client_id: str,
            *,
            add: list[str] | tuple[str, ...] = (),
            optional: list[str] | tuple[str, ...] = (),
    ) -> "RealmBuilder":
        client = self._get_client(client_id)
        # KC fields on ClientRepresentation
        dfl = set(getattr(client, "defaultClientScopes", []) or [])
        opt = set(getattr(client, "optionalClientScopes", []) or [])
        dfl.update(add or [])
        opt.update(optional or [])
        if dfl:
            client.defaultClientScopes = sorted(dfl)
        if opt:
            client.optionalClientScopes = sorted(opt)
        LOG.debug("Client '%s' scopes: default=%s optional=%s",
                  client_id, client.defaultClientScopes, client.optionalClientScopes)
        return self

    def set_client_full_scope_allowed(self, client_id: str, value: bool = True) -> "RealmBuilder":
        client = self._get_client(client_id)
        client.fullScopeAllowed = bool(value)
        LOG.debug("Client '%s' fullScopeAllowed=%s", client_id, client.fullScopeAllowed)
        return self

    def add_users_from_rbac_positions_file(
            self,
            path: str,
            *,
            email_domain: str = "example.org",
            include_description_attribute: bool = True,
            password: Optional[str] = None,  # NEW
            temporary_password: bool = False,  # NEW
            password_field: str = "password",  # NEW
            encoding: str = "utf-8",
    ) -> "RealmBuilder":
        import json as _json
        from pathlib import Path as _Path
        with _Path(path).expanduser().open("r", encoding=encoding) as f:
            rbac = _json.load(f)
        return self.add_users_from_rbac_positions(
            rbac,
            email_domain=email_domain,
            include_description_attribute=include_description_attribute,
            password=password,
            temporary_password=temporary_password,
            password_field=password_field,
        )

    # --- client scopes ---
    def add_client_scope(
        self,
        name: str,
        *,
        id: Optional[str] = None,
        description: Optional[str] = None,
        protocol: str = "openid-connect",
        attributes: Optional[Dict[str, Any]] = None,
        protocol_mappers: Optional[List[ProtocolMapperRepresentation]] = None,
        **kwargs,
    ) -> "RealmBuilder":
        if protocol_mappers is None and "protocolMappers" in kwargs:
            protocol_mappers = kwargs["protocolMappers"]
        self.realm.clientScopes.append(
            ClientScopeRepresentation(
                id=id,
                name=name,
                description=description,
                protocol=protocol,
                attributes=attributes or {},
                protocolMappers=protocol_mappers or [],
            )
        )
        LOG.debug("Added client scope: %s (total=%d)", name, len(self.realm.clientScopes))
        return self

    def ensure_client_scope(
        self,
        name: str,
        *,
        id: Optional[str] = None,
        description: Optional[str] = None,
        protocol: str = "openid-connect",
        attributes: Optional[Dict[str, Any]] = None,
        protocol_mappers: Optional[List[ProtocolMapperRepresentation]] = None,
        **kwargs,
    ) -> "RealmBuilder":
        for cs in self.realm.clientScopes:
            if cs.name == name:
                return self
        return self.add_client_scope(
            name,
            id=id,
            description=description,
            protocol=protocol,
            attributes=attributes,
            protocol_mappers=protocol_mappers,
            **kwargs,
        )

    def add_builtin_oidc_scopes(self) -> "RealmBuilder":
        LOG.debug("Skipping built-in scopes; Keycloak will create them.")
        return self

    # --- export ---
    def export(self) -> Dict[str, Any]:
        data = self.realm.model_dump(exclude_none=True)
        LOG.debug(
            "export(): clients=%d, clientScopes=%d, roles=%d, users=%d",
            len(self.realm.clients), len(self.realm.clientScopes),
            len(self.realm.roles.realm), len(self.realm.users)
        )
        return data

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def make_email_client_scope(include_in_token_scope: bool = True) -> ClientScopeRepresentation:
    return ClientScopeRepresentation(
        name="email",
        protocol="openid-connect",
        attributes={"include.in.token.scope": str(include_in_token_scope).lower()},
        protocolMappers=[
            ProtocolMapperRepresentation(
                name="email",
                protocolMapper="oidc-usermodel-property-mapper",
                config={
                    "userinfo.token.claim": "true",
                    "user.attribute": "email",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "claim.name": "email",
                    "jsonType.label": "String",
                },
            )
        ],
    )

# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build a Keycloak realm export JSON (debug-friendly)")
    parser.add_argument("--name", default="OSSS", help="Realm name")
    parser.add_argument("--out", default="realm-export.json", help="Output file path")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging (or KC_DEBUG=1)")
    parser.add_argument("--trace", action="store_true", help="Ultra-verbose logging below DEBUG")
    parser.add_argument("--skip-email-scope", action="store_true", help="Do not add 'email' client scope")
    args = parser.parse_args()

    configure_logging(debug=args.debug, trace=args.trace)
    LOG.info("Starting builder for realm '%s'", args.name)

    rb = RealmBuilder(args.name)


    # --- Realm roles ---
    rb.add_realm_role("offline_access", "Offline Access", composite=False)
    rb.add_realm_role("uma_authorization", "UMA Authorization", composite=False)


    if not args.skip_email_scope:
        cs = make_email_client_scope()
        rb.add_client_scope(
            name=cs.name,
            id=cs.id,
            description=cs.description,
            protocol=cs.protocol,
            attributes=cs.attributes,
            protocol_mappers=cs.protocolMappers,
        )

    # Ensure built-ins user asked for
    rb.add_builtin_oidc_scopes()

    # Composite default-roles for this realm
    rb.add_realm_role(
        "default-roles-test",
        "Default test role",
        composite=True,
        composites={
            "realm": ["offline_access", "uma_authorization"],
            "client": {
                "account": ["manage-account", "delete-account"],
                "realm-management": [
                    "query-groups", "manage-clients", "realm-admin", "manage-users",
                    "query-realms", "view-events", "view-realm", "view-clients",
                    "manage-events", "create-client", "manage-identity-providers",
                    "manage-authorization", "query-users", "view-identity-providers",
                    "impersonation", "query-clients", "view-authorization",
                    "manage-realm", "view-users",
                ],
            },
        },
    )

    # --- Clients ---

    # Primary test client: allow password + auth code for tests
    rb.add_client(
        client_id="osss-api",
        name="osss-api",
        redirect_uris=["http://localhost:8081/*"],
        protocol = "openid-connect",
        web_origins=["+"],
        public_client=False,
        direct_access_grants_enabled=True,  # password grant
        service_accounts_enabled=True,
        standard_flow_enabled=False,  # authorization code flow
        client_authenticator_type="client-secret",
        authorization_services_enabled=True,
        secret="password",
        attributes={
            # These mirror common defaults; not all are required for tests.
            "id.token.as.detached.signature": "false",
            "saml.assertion.signature": "false",
            "saml.force.post.binding": "false",
            "saml.multivalued.roles": "false",
            "saml.encrypt": "false",
            "oauth2.device.authorization.grant.enabled": "false",
            "backchannel.logout.revoke.offline.tokens": "false",
            "saml.server.signature": "false",
            "saml.server.signature.keyinfo.ext": "false",
            "use.refresh.tokens": "true",
            "exclude.session.state.from.auth.response": "false",
            "oidc.ciba.grant.enabled": "false",
            "saml.artifact.binding": "false",
            "backchannel.logout.session.required": "true",
            "client_credentials.use_refresh_token": "false",
            "saml_force_name_id_format": "false",
            "require.pushed.authorization.requests": "false",
            "saml.client.signature": "false",
            "tls.client.certificate.bound.access.tokens": "false",
            "saml.authnstatement": "false",
            "display.on.consent.screen": "false",
            "saml.onetimeuse.condition": "false",
        },
        default_client_scopes=["roles", "profile", "email", "osss-api-roles"],
        optional_client_scopes=["address", "offline_access"],
        authorization_settings={
            "allowRemoteResourceManagement": True,
            "policyEnforcementMode": "ENFORCING",
            "resources": [
                {
                    "name": "Default Resource",
                    "type": "urn:osss-api:resources:default",
                    "ownerManagedAccess": False,
                    "attributes": {},
                    "uris": ["/*"],
                }
            ],
            "policies": [],
            "scopes": [],
            "decisionStrategy": "UNANIMOUS",
        },

    )

    rb.add_client(
        client_id="osss-web",
        name="osss-web",
        root_url="http://localhost:3000",
        base_url="/",
        admin_url="http://localhost:3000",
        redirect_uris=["http://localhost:3000/*","http://localhost:3000/api/auth/callback/keycloak"],
        web_origins=["http://localhost:3000"],
        protocol="openid-connect",
        public_client=False,
        bearer_only=False,
        direct_access_grants_enabled=False,  # password grant
        service_accounts_enabled=False,
        standard_flow_enabled=True,  # authorization code flow
        client_authenticator_type="client-secret",
        authorization_services_enabled=True,
        implicit_flow_enabled=False,
        secret="password",
        attributes={"post.logout.redirect.uris": "http://localhost:3000/"},
        default_client_scopes=[
            "profile",
            "email",
            "roles",
            "osss-api-audience",
            "osss-api-roles"
        ],
        optional_client_scopes=["address", "offline_access"],
        protocol_mappers=[
            ProtocolMapperRepresentation(
                name="username",
                protocolMapper="oidc-usermodel-property-mapper",
                config={
                    "userinfo.token.claim": "true",
                    "user.attribute": "username",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "claim.name": "preferred_username",
                    "jsonType.label": "String"
                },
            ),
        ]

    )

    # admin-cli client (service accounts on; no browser flow)
    rb.add_client(
        client_id="admin-cli",
        name="admin-cli",
        protocol="openid-connect",
        public_client=False,
        service_accounts_enabled=True,
        standard_flow_enabled=False,
        direct_access_grants_enabled=False,
        bearer_only=False,
        client_authenticator_type="client-secret",
        secret="password",
        enabled=True,
        full_scope_allowed=True,
        default_client_scopes=["roles", "profile", "email", "roles"],
        optional_client_scopes=["address", "offline_access"],
        authorization_services_enabled=True,
        attributes={
            "id.token.as.detached.signature": "false",
            "saml.assertion.signature": "false",
            "saml.force.post.binding": "false",
            "saml.multivalued.roles": "false",
            "saml.encrypt": "false",
            "oauth2.device.authorization.grant.enabled": "true",
            "backchannel.logout.revoke.offline.tokens": "false",
            "saml.server.signature": "false",
            "saml.server.signature.keyinfo.ext": "false",
            "use.refresh.tokens": "true",
            "exclude.session.state.from.auth.response": "false",
            "oidc.ciba.grant.enabled": "false",
            "saml.artifact.binding": "false",
            "backchannel.logout.session.required": "false",
            "client_credentials.use_refresh_token": "false",
            "saml_force_name_id_format": "false",
            "require.pushed.authorization.requests": "false",
            "saml.client.signature": "false",
            "tls.client.certificate.bound.access.tokens": "false",
            "saml.authnstatement": "false",
            "display.on.consent.screen": "false",
            "saml.onetimeuse.condition": "false",
        },
        authorization_settings={
            "allowRemoteResourceManagement": True,
            "policyEnforcementMode": "ENFORCING",
            "resources": [
                {
                    "name": "Default Resource",
                    "type": "urn:osss-api:resources:default",
                    "ownerManagedAccess": False,
                    "attributes": {},
                    "uris": ["/*"],
                }
            ],
            "policies": [],
            "scopes": [],
            "decisionStrategy": "UNANIMOUS",
        },
    )

    # --- Client scopes (define explicit mappers so tokens contain claims) ---



    # Add a client scope that injects aud=osss-api into access tokens
    rb.add_client_scope(
        name="osss-api-audience",
        description="Adds aud=osss-api to access tokens",
        protocol="openid-connect",
        attributes={
            "include.in.token.scope": "true",
        },
        protocol_mappers=[
            ProtocolMapperRepresentation(
                name="audience: osss-api",
                protocol="openid-connect",
                protocolMapper="oidc-audience-mapper",
                consentRequired=False,
                config={
                    "access.token.claim": "true",
                    "id.token.claim": "false",
                    "included.client.audience": "osss-api",
                },
            )
        ],
    )

    # profile: basic profile fields
    rb.add_client_scope(
        name="profile",
        protocol="openid-connect",
        attributes={"include.in.token.scope": "true"},
        protocol_mappers=[
            ProtocolMapperRepresentation(
                name="given name",
                protocolMapper="oidc-usermodel-property-mapper",
                config={
                    "user.attribute": "firstName",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true",
                    "claim.name": "given_name",
                    "jsonType.label": "String",
                },
            ),
            ProtocolMapperRepresentation(
                name="family name",
                protocolMapper="oidc-usermodel-property-mapper",
                config={
                    "user.attribute": "lastName",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true",
                    "claim.name": "family_name",
                    "jsonType.label": "String",
                },
            ),
            ProtocolMapperRepresentation(
                name="preferred username",
                protocolMapper="oidc-usermodel-property-mapper",
                config={
                    "user.attribute": "username",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true",
                    "claim.name": "preferred_username",
                    "jsonType.label": "String",
                },
            ),
        ],
    )

    rb.add_client_role("osss-api", "api.user", description="Baseline access to OSSS API")
    rb.add_client_role("osss-api", "api.admin", description="Administrative access to OSSS API")
    rb.add_client_role(
        "osss-api",
        "api.teacher",
        description="Teacher access to OSSS API",
        attributes={
            "allowed_schools": ["Heritage Elementary", "Oak View MS"],
            "grade_bands": ["6-8"],
            "scopes": ["students:read", "attendance:read", "roster:read"],
            "max_results": ["1000"],
        }
    )

    # --- Rebuild DBML from models ----
    import_all_models("OSSS.db.models")
    # Import the Base that models registered on
    try:
        base_mod = importlib.import_module("OSSS.db.base")
        Base = getattr(base_mod, "Base")
    except Exception as exc:
        raise SystemExit(f"Could not import OSSS.db.base: {exc}")

    md: sa.MetaData = Base.metadata

    # Build DBML
    chunks = []
    # Sort tables for stable output
    for tname in sorted(md.tables.keys()):
        table = md.tables[tname]
        chunks.append(emit_table_dbml(table))

    # Refs last
    chunks.append("")
    chunks.append(emit_refs_dbml(md))

    dbml = "\n\n".join(chunks).strip() + "\n"

    with open("data_model/schema.dbml", "w", encoding="utf-8") as f:
        f.write(dbml)

    # ---- Read database table names from dbml
    text = read_dbml_file("data_model/schema.dbml")
    table_names = list(iter_table_names(text))
    table_names = list(dict.fromkeys(table_names))  # preserve first-seen order
    print(json.dumps(table_names, indent=2))

    for table in table_names:
        rb.add_client_role(
            "osss-api",
            f"read:{table}",
            description="Read " + str(table),
            attributes={
                "allowed_schools": ["All"],
                "grade_bands": ["k-12"],
                # "scopes": ["students:read", "attendance:read", "roster:read"],
                "max_results": "1000",
            },
        )

        rb.add_client_role(
            "osss-api",
            f"manage:{table}",
            description="Manage " + str(table),
            attributes={
                "allowed_schools": ["All"],
                "grade_bands": ["k-12"],
                # "scopes": ["students:read", "attendance:read", "roster:read"],
                "max_results": "1000",
            },
        )

    path = Path("RBAC.json")  # replace with your file
    with path.open("r", encoding="utf-8") as f:
        organizational_structure = json.load(f)  # dict or list

    rb.add_groups_from_hierarchy(organizational_structure, role_client_id="osss-api")

    rb.ensure_client_default_scopes(
        "osss-api",
        add=["roles", "profile", "email"]  # 'roles' is the important one
    )

    rb.ensure_client_default_scopes(
        "osss-web",
        add=["roles", "profile", "email"]  # 'roles' is the important one
    )

    rb.add_builtin_oidc_scopes()  # currently creates names only (no mappers) :contentReference[oaicite:2]{index=2}
    rb.ensure_roles_scope_with_mappers()
    rb.ensure_client_roles_scope("osss-api", scope_name="osss-api-roles")
    rb.ensure_client_roles_scope("osss-web", scope_name="osss-web-roles")



    # then add users for each `position_*`
    rb.add_users_from_rbac_positions_file(
        "RBAC.json",
        email_domain="osss.local",
        password="password",
        temporary_password=False
    )

    rb.add_user(
        username="teacher@osss.local",
        email="teacher@osss.local",
        first_name="Pat",
        last_name="Teacher",
        enabled=True,
        totp=False,
        email_verified=True,
        password="password",
        temporary_password=False,
        realm_roles=["uma_authorization"],
        client_roles={
            "account": ["view-profile"],
            "osss-api": ["api.user", "api.teacher"],  # create a "user" role on your osss-api
        },
        attributes={"role": ["teacher"]},
    )

    out = rb.export()

    # with this (singular name, if that's how you defined it):
    out = rb._finalize_for_export()

    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    LOG.info("Wrote realm export to %s", args.out)

# ---- RealmBuilder override/refactor shim ------------------------------------
from typing import Mapping, Any, Callable

# Determine a base "build-like" method, even if it's not literally named "build"
_base_build_method: Callable | None = None
for _cand in ("build", "render", "to_dict", "as_dict", "export", "dump", "generate", "compile", "build_realm", "create"):
    if hasattr(RealmBuilder, _cand) and callable(getattr(RealmBuilder, _cand)):
        _base_build_method = getattr(RealmBuilder, _cand)
        _base_build_name = _cand
        break
else:
    _base_build_name = None

# Per-instance overrides (top-level realm fields to merge)
if not hasattr(RealmBuilder, "_overrides"):
    # Will be attached in __init__ wrapper below
    pass

# Chainable .update(mapping=None, **kwargs)
if not hasattr(RealmBuilder, "update"):
    def _rb_update(self, mapping: Mapping[str, Any] | None = None, /, **kwargs: Any):
        """
        Chainable: attach/merge arbitrary top-level realm overrides that will be
        applied after the base realm is built.
        Usage:
            builder.update({"foo": 1}).update(bar=2)
        """
        if getattr(self, "_overrides", None) is None:
            self._overrides = {}
        if mapping:
            self._overrides.update(dict(mapping))
        if kwargs:
            self._overrides.update(kwargs)
        return self
    RealmBuilder.update = _rb_update  # type: ignore[attr-defined]

# Sugar: set session TTLs
if not hasattr(RealmBuilder, "with_session_timeouts"):
    def _rb_with_session_timeouts(self, *, idle: int, max_lifespan: int, offline_idle: int):
        """
        Convenience wrapper for common Keycloak realm session TTLs.
        """
        return self.update(
            ssoSessionIdleTimeout=idle,
            ssoSessionMaxLifespan=max_lifespan,
            offlineSessionIdleTimeout=offline_idle,
        )
    RealmBuilder.with_session_timeouts = _rb_with_session_timeouts  # type: ignore[attr-defined]

# Wrap __init__ to ensure each instance gets its own _overrides dict
if not hasattr(RealmBuilder, "_orig_init"):
    RealmBuilder._orig_init = RealmBuilder.__init__  # type: ignore[attr-defined]
    def _rb_init(self, *args, **kwargs):
        RealmBuilder._orig_init(self, *args, **kwargs)  # type: ignore[attr-defined]
        if getattr(self, "_overrides", None) is None:
            self._overrides = {}
    RealmBuilder.__init__ = _rb_init  # type: ignore[attr-defined]

def _normalize_realm_dict(realm: Any) -> dict:
    # Normalize to a plain dict (supports Pydantic v1/v2, dataclasses, etc.)
    if hasattr(realm, "model_dump"):   # pydantic v2
        realm = realm.model_dump()
    elif hasattr(realm, "dict"):       # pydantic v1
        realm = realm.dict()
    elif hasattr(realm, "__dict__") and not isinstance(realm, dict):
        realm = dict(realm.__dict__)
    if not isinstance(realm, dict):
        raise TypeError("RealmBuilder build/render must produce a dict-like structure")
    return realm

# Wrap/define build:
if _base_build_method is not None:
    # Preserve the original "build-like" for later calls
    if not hasattr(RealmBuilder, "_orig_build"):
        RealmBuilder._orig_build = _base_build_method  # type: ignore[attr-defined]

    def _rb_build(self, *args, **kwargs):
        realm = RealmBuilder._orig_build(self, *args, **kwargs)  # type: ignore[attr-defined]
        realm = _normalize_realm_dict(realm)
        overrides = getattr(self, "_overrides", None) or {}
        if overrides:
            realm.update(overrides)
        return realm

    # If there is already a .build(), wrap it; otherwise, provide a .build() alias
    if _base_build_name == "build":
        RealmBuilder.build = _rb_build  # type: ignore[attr-defined]
    else:
        # Keep the original method intact, and also expose a new .build()
        if not hasattr(RealmBuilder, "build"):
            RealmBuilder.build = _rb_build  # type: ignore[attr-defined]
else:
    # No build-like method found; define a minimal build() pulling from common attrs
    if not hasattr(RealmBuilder, "build"):
        def _rb_build_min(self):
            for attr in ("realm", "data", "payload", "config"):
                if hasattr(self, attr):
                    realm = getattr(self, attr)
                    realm = _normalize_realm_dict(realm)
                    overrides = getattr(self, "_overrides", None) or {}
                    if overrides:
                        realm.update(overrides)
                    return realm
            raise AttributeError(
                "RealmBuilder has no build-like method and no common realm/data attributes; "
                "please implement .build() or one of: render, to_dict, as_dict, export, dump, generate, compile."
            )
        RealmBuilder.build = _rb_build_min  # type: ignore[attr-defined]
# -----------------------------------------------------------------------------
