#!/usr/bin/env python3
"""
build_realm.py

An object-oriented builder for generating a Keycloak `realm-export.json`
suitable for import during container start (e.g., via `--import-realm` or
Keycloak's auto-import at `/opt/keycloak/data/import`).

Why this script exists
----------------------
Keycloak ships with *built-in* OIDC client scopes like `roles`, `profile`,
and `email`. If your realm import doesn't include those scopes (or you forget
to attach them as default client scopes), your access tokens may *lack* key
claims like:

- `realm_access.roles` (realm roles)
- `resource_access.{client_id}.roles` (client roles)
- `email` / `email_verified`
- `given_name` / `family_name` / `preferred_username`

This builder ensures:
1) The realm includes the scopes `roles`, `email`, and `profile` with explicit
   protocol mappers (so the claims are present in tokens), and
2) Clients include those scopes as *default* client scopes.

Quickstart
----------
    python build_realm.py

This writes `<repo_root>/realm-export.json`, which your docker-compose
can mount into the Keycloak container to create/overwrite the realm.

Pydantic
--------
This file targets **Pydantic v2**. (Your project pins `pydantic>=2.6`.)
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, ConfigDict, model_validator


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def _uuid() -> str:
    """Generate a random UUID string (used for Keycloak ids when omitted)."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------
# Pydantic models – simplified mirrors of Keycloak export JSON
# (v2-style models; unknown fields are ignored for resilience)
# ---------------------------------------------------------------------

class RoleRepresentation(BaseModel):
    """
    Keycloak role (realm or client role).
    """
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
    def _ensure_id_and_attrs(self) -> "RoleRepresentation":
        # Make sure Keycloak sees a proper id + always a dict for attributes.
        if not self.id:
            self.id = _uuid()
        if self.attributes is None:
            self.attributes = {}
        return self


class RequiredActionProviderRepresentation(BaseModel):
    """
    Realm-level Required Action (e.g., CONFIGURE_TOTP). Not heavily used here,
    but kept for completeness/extensibility.
    """
    alias: str
    name: str
    providerId: str
    enabled: bool = True
    defaultAction: bool = False
    priority: int = 0
    config: Dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


class AuthenticatorConfigRepresentation(BaseModel):
    """
    Optional authenticator config entries, if you add flows.
    """
    id: str = Field(default_factory=_uuid)
    alias: str
    config: Dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


class DefaultRoleRepresentation(BaseModel):
    """
    Default composite role assigned to new users (Keycloak creates one per realm).
    """
    id: str = Field(default_factory=_uuid)
    name: str
    description: Optional[str] = None
    composite: bool = True
    clientRole: bool = False
    containerId: Optional[str] = None


class RolesRepresentation(BaseModel):
    """
    Container for realm roles and client roles.
    """
    realm: List[RoleRepresentation] = Field(default_factory=list)
    client: Dict[str, List[RoleRepresentation]] = Field(
        default_factory=lambda: {
            # Keep entries for these commonly-seen clients around, but empty
            "account-console": [],
            "broker": [],
            "admin-cli": [],
            "security-admin-console": [],
        }
    )

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def _ensure_id_attributes_everywhere(self) -> "RolesRepresentation":
        # Realm roles
        for r in self.realm:
            if not r.id:
                r.id = _uuid()
            if r.attributes is None:
                r.attributes = {}
        # Client roles
        for roles in self.client.values():
            for r in roles:
                if not r.id:
                    r.id = _uuid()
                if r.attributes is None:
                    r.attributes = {}
        return self


class CredentialRepresentation(BaseModel):
    """User credential declaration (we only use simple 'password')."""
    type: str = "password"
    value: Optional[str] = None
    temporary: bool = False


class UserRepresentation(BaseModel):
    """
    Realm user. Only the most common fields are modeled here.
    """
    id: str = Field(default_factory=_uuid)
    username: str
    enabled: bool = True
    email: Optional[str] = None
    emailVerified: bool = False
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    requiredActions: List[str] = Field(default_factory=list)
    credentials: Optional[List[CredentialRepresentation]] = None

    # Role assignments by *name* (Keycloak resolves on import)
    realmRoles: Optional[List[str]] = None
    clientRoles: Dict[str, List[str]] = Field(default_factory=dict)

    groups: List[str] = Field(default_factory=list)
    attributes: Optional[Dict[str, Any]] = None

    # Extra optional exports commonly present
    totp: Optional[bool] = None
    disableableCredentialTypes: Optional[List[str]] = None
    notBefore: Optional[int] = None
    createdTimestamp: Optional[int] = None
    serviceAccountClientId: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class ProtocolMapperRepresentation(BaseModel):
    """
    OIDC (or SAML) protocol mapper definition.
    For OIDC, common mappers are:
      - oidc-usermodel-realm-role-mapper
      - oidc-usermodel-client-role-mapper
      - oidc-usermodel-property-mapper
    """
    id: Optional[str] = None
    name: str
    protocol: str = "openid-connect"
    protocolMapper: str
    consentRequired: bool = False
    config: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


class ClientRepresentation(BaseModel):
    """
    Keycloak Client configuration (OIDC).
    """
    id: Optional[str] = None
    clientId: str
    name: Optional[str] = None

    # URLs + app model
    rootUrl: Optional[str] = None
    baseUrl: Optional[str] = None

    # Auth + switches
    enabled: bool = True
    clientAuthenticatorType: str = "client-secret"
    secret: Optional[str] = None
    publicClient: bool = False
    bearerOnly: bool = False
    frontchannelLogout: bool = False
    standardFlowEnabled: bool = True
    directAccessGrantsEnabled: bool = False
    implicitFlowEnabled: bool = False
    serviceAccountsEnabled: bool = False
    consentRequired: bool = False
    fullScopeAllowed: bool = True

    # CORS + redirects
    redirectUris: List[str] = Field(default_factory=list)
    webOrigins: List[str] = Field(default_factory=list)

    # Misc
    notBefore: int = 0
    alwaysDisplayInConsole: bool = False
    surrogateAuthRequired: bool = False
    nodeReRegistrationTimeout: int = 0
    protocol: str = "openid-connect"
    attributes: Dict[str, Any] = Field(default_factory=dict)
    authenticationFlowBindingOverrides: Dict[str, Any] = Field(default_factory=dict)

    # Scopes/mappers
    protocolMappers: Optional[List[ProtocolMapperRepresentation]] = None
    defaultClientScopes: Optional[List[str]] = None
    optionalClientScopes: Optional[List[str]] = None

    # Authz services (optional)
    authorizationServicesEnabled: Optional[bool] = None
    authorizationSettings: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="ignore")



class GroupRepresentation(BaseModel):
    """
    Realm group tree. Only a subset of fields are modeled.
    """
    id: Optional[str] = None
    name: str
    path: Optional[str] = None
    attributes: Optional[Dict[str, List[str]]] = None
    realmRoles: Optional[List[str]] = None
    clientRoles: Optional[Dict[str, List[str]]] = None
    subGroups: Optional[List["GroupRepresentation"]] = None  # forward-ref

    model_config = ConfigDict(extra="ignore")


# resolve forward refs (Pydantic v2)
try:
    GroupRepresentation.model_rebuild()
except Exception:
    pass


class AuthenticationExecutionRepresentation(BaseModel):
    """Skeleton auth execution step (kept for future extension)."""
    authenticator: Optional[str] = None
    authenticatorConfig: Optional[str] = None
    authenticatorFlow: bool = False
    requirement: str
    priority: int
    flowAlias: Optional[str] = None
    userSetupAllowed: bool = False
    autheticatorFlow: bool = False  # spelling as in export

    model_config = ConfigDict(extra="ignore")


class AuthenticationFlowRepresentation(BaseModel):
    """Skeleton flow (not actively used here)."""
    id: str
    alias: str
    description: Optional[str] = None
    providerId: str
    topLevel: bool
    builtIn: bool
    authenticationExecutions: List[AuthenticationExecutionRepresentation]

    model_config = ConfigDict(extra="ignore")


class ScopeMappingRepresentation(BaseModel):
    """Link a client scope to realm roles (rarely needed here)."""
    clientScope: str
    roles: List[str]

    model_config = ConfigDict(extra="ignore")


class ClientScopeRepresentation(BaseModel):
    """
    OIDC client scope with optional protocol mappers.
    """
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    protocol: str = "openid-connect"
    attributes: Dict[str, Any] = Field(default_factory=dict)
    protocolMappers: List[ProtocolMapperRepresentation] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class RealmRepresentation(BaseModel):
    """
    The full realm export. Only a subset of fields are modeled to keep the
    JSON concise but sufficiently rich for tests/integration.
    """
    id: Optional[str] = None
    realm: str
    enabled: bool = True

    # Core collections
    roles: RolesRepresentation = Field(default_factory=RolesRepresentation)
    users: List[UserRepresentation] = Field(default_factory=list)
    clients: List[ClientRepresentation] = Field(default_factory=list)
    groups: List[GroupRepresentation] = Field(default_factory=list)

    # Scopes + mappers
    scopeMappings: List[ScopeMappingRepresentation] = Field(default_factory=list)
    clientScopes: List[ClientScopeRepresentation] = Field(default_factory=list)

    # Config odds & ends
    components: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    authenticatorConfig: List[AuthenticatorConfigRepresentation] = Field(default_factory=list)
    requiredActions: List[RequiredActionProviderRepresentation] = Field(default_factory=list)
    browserSecurityHeaders: Dict[str, str] = Field(default_factory=dict)
    smtpServer: Dict[str, str] = Field(default_factory=dict)

    # Events / providers
    eventsEnabled: bool = False
    eventsListeners: List[str] = Field(default_factory=list)
    enabledEventTypes: List[str] = Field(default_factory=list)
    adminEventsEnabled: bool = False
    adminEventsDetailsEnabled: bool = False
    identityProviders: List[dict] = Field(default_factory=list)
    identityProviderMappers: List[dict] = Field(default_factory=list)

    # i18n
    internationalizationEnabled: bool = False
    supportedLocales: List[str] = Field(default_factory=list)

    # Flow bindings (keep defaults)
    browserFlow: str = "browser"
    registrationFlow: str = "registration"
    directGrantFlow: str = "direct grant"
    resetCredentialsFlow: str = "reset credentials"
    clientAuthenticationFlow: str = "clients"
    dockerAuthenticationFlow: str = "docker auth"

    # Default composite role
    defaultRole: DefaultRoleRepresentation = Field(
        default_factory=lambda: DefaultRoleRepresentation(
            name="default-roles-test",
            description="${role_default-roles}",
            composite=True,
            clientRole=False,
            containerId="OSSS",
        )
    )

    # Token / session lifetimes (trimmed to essentials)
    defaultSignatureAlgorithm: Optional[str] = "RS256"
    accessTokenLifespan: Optional[int] = 300
    accessTokenLifespanForImplicitFlow: Optional[int] = 900
    ssoSessionIdleTimeout: Optional[int] = 1800
    ssoSessionMaxLifespan: Optional[int] = 36000

    # OTP (left at Keycloak defaults)
    otpPolicyType: str = "totp"
    otpPolicyAlgorithm: str = "HmacSHA1"
    otpPolicyInitialCounter: int = 0
    otpPolicyDigits: int = 6
    otpPolicyLookAheadWindow: int = 1
    otpPolicyPeriod: int = 30
    otpSupportedApplications: List[str] = Field(
        default_factory=lambda: ["FreeOTP", "Google Authenticator"]
    )

    # Misc realm flags
    keycloakVersion: str = "16.1.0"
    userManagedAccessAllowed: bool = False

    # Default client scopes applied to *every* client in this realm (by name)
    defaultDefaultClientScopes: List[str] = Field(default_factory=list)
    defaultOptionalClientScopes: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


# ---------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------

class RealmBuilder:
    """
    Fluent builder that assembles a minimal yet functional realm, with
    explicit OIDC client scopes/mappers so tests get the right token claims.
    """
    def __init__(self, name: str, enabled: bool = True):
        self.realm = RealmRepresentation(realm=name, enabled=enabled)

    # ----- Required actions / auth config (optional plumbing) -----

    def add_required_action(
        self,
        *,
        alias: str,
        name: str,
        provider_id: str,
        enabled: bool = True,
        default_action: bool = False,
        priority: int = 0,
        config: Optional[dict] = None,
    ) -> "RealmBuilder":
        self.realm.requiredActions.append(
            RequiredActionProviderRepresentation(
                alias=alias,
                name=name,
                providerId=provider_id,
                enabled=enabled,
                defaultAction=default_action,
                priority=priority,
                config=config or {},
            )
        )
        return self

    def add_authenticator_config(self, config: AuthenticatorConfigRepresentation) -> "RealmBuilder":
        self.realm.authenticatorConfig.append(config)
        return self

    # ----- Components / SMTP / Events (optional; no-ops here) -----

    def add_component(self, provider_category: str, component: Dict[str, Any]) -> "RealmBuilder":
        self.realm.components.setdefault(provider_category, []).append(component)
        return self

    def set_components(self, components: Dict[str, List[Dict[str, Any]]]) -> "RealmBuilder":
        self.realm.components = components
        return self

    def set_smtp_server(self, config: Dict[str, str]) -> "RealmBuilder":
        self.realm.smtpServer = config
        return self

    def enable_events(self, listeners: List[str], enabled_types: Optional[List[str]] = None) -> "RealmBuilder":
        self.realm.eventsEnabled = True
        self.realm.eventsListeners = listeners
        if enabled_types:
            self.realm.enabledEventTypes = enabled_types
        return self

    def enable_admin_events(self, details: bool = False) -> "RealmBuilder":
        self.realm.adminEventsEnabled = True
        self.realm.adminEventsDetailsEnabled = details
        return self

    def add_identity_provider(self, provider: dict) -> "RealmBuilder":
        self.realm.identityProviders.append(provider)
        return self

    def add_identity_provider_mapper(self, mapper: dict) -> "RealmBuilder":
        self.realm.identityProviderMappers.append(mapper)
        return self

    def set_default_default_client_scopes(self, scopes: List[str]) -> "RealmBuilder":
        """
        Scopes applied to all clients by default (realm-level setting).
        """
        self.realm.defaultDefaultClientScopes = scopes
        return self

    def set_default_optional_client_scopes(self, scopes: List[str]) -> "RealmBuilder":
        """
        Optional scopes a client may opt into (realm-level setting).
        """
        self.realm.defaultOptionalClientScopes = scopes
        return self

    # ----- Roles -----

    def add_realm_role(
        self,
        name: str,
        description: Optional[str] = None,
        composite: bool = False,
        composites: Optional[Dict[str, Any]] = None,
        role_id: Optional[str] = None,
    ) -> "RealmBuilder":
        self.realm.roles.realm.append(
            RoleRepresentation(
                id=role_id,
                name=name,
                description=description,
                composite=composite,
                clientRole=False,
                containerId=self.realm.realm,
                composites=composites,
            )
        )
        return self

    def add_client_role(
        self,
        client_id: str,
        role_name: str,
        *,
        description: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> "RealmBuilder":
        # 1) ensure roles container
        _ensure_roles_container(self.realm)

        # 2) point to the client-roles bucket (dict or model)
        roles = self.realm.roles
        if isinstance(roles, dict):
            client_roles_map = roles["client"]
        else:
            client_roles_map = roles.client  # pydantic model

        # 3) ensure list for this clientId
        if client_id not in client_roles_map or client_roles_map[client_id] is None:
            client_roles_map[client_id] = []

        role_list = client_roles_map[client_id]

        # 4) no-dup
        def _name_of(r):
            return r.get("name") if isinstance(r, dict) else getattr(r, "name", None)
        if any(_name_of(r) == role_name for r in role_list):
            return self

        # 5) normalize attributes and append
        norm_attrs = _norm_role_attrs(attributes)

        role_repr = RoleRepresentation(
            name=role_name,
            description=description,
            composite=False,
            clientRole=True,
            containerId=client_id,
            attributes=norm_attrs,
        )
        role_list.append(role_repr)
        return self

    # ----- Clients -----

    def add_client(
        self,
        client_id: str,
        *,
        id: Optional[str] = None,
        name: Optional[str] = None,
        secret: Optional[str] = None,
        redirect_uris: Optional[List[str]] = None,
        web_origins: Optional[List[str]] = None,
        base_url: Optional[str] = None,
        admin_url: Optional[str] = None,
        public_client: bool = False,
        direct_access_grants_enabled: bool = False,
        service_accounts_enabled: bool = False,
        standard_flow_enabled: bool = True,
        attributes: Optional[Dict[str, Any]] = None,
        default_client_scopes: Optional[List[str]] = None,
        optional_client_scopes: Optional[List[str]] = None,
        protocol_mappers: Optional[List[Union[ProtocolMapperRepresentation, Dict[str, Any]]]] = None,
        authorization_services_enabled: Optional[bool] = None,
        authorization_settings: Optional[Dict[str, Any]] = None,
        root_url: Optional[str] = None,
        bearer_only: Optional[bool] = None,
        full_scope_allowed: Optional[bool] = None,
        node_re_registration_timeout: Optional[int] = None,
        authentication_flow_binding_overrides: Optional[Dict[str, Any]] = None,
        frontchannel_logout: Optional[bool] = None,
        consent_required: Optional[bool] = None,
        implicit_flow_enabled: Optional[bool] = None,
        not_before: Optional[int] = None,
        enabled: Optional[bool] = None,
        always_display_in_console: Optional[bool] = None,
        client_authenticator_type: Optional[str] = None,
        surrogate_auth_required: Optional[bool] = None,
        protocol: str = "openid-connect",

    ) -> "RealmBuilder":
        # Normalize protocol mappers to actual objects (dicts or instances are ok).
        pm_norm: Optional[List[ProtocolMapperRepresentation]] = None
        if protocol_mappers is not None:
            pm_norm = []
            for pm in protocol_mappers:
                if isinstance(pm, ProtocolMapperRepresentation):
                    pm_norm.append(pm)
                else:
                    pm_norm.append(ProtocolMapperRepresentation(**pm))

        self.realm.clients.append(
            ClientRepresentation(
                id=id,
                clientId=client_id,
                name=name,
                secret=secret,
                redirectUris=redirect_uris or [],
                webOrigins=web_origins or [],
                baseUrl=base_url,
                adminUrl=admin_url,
                publicClient=public_client,
                directAccessGrantsEnabled=direct_access_grants_enabled,
                serviceAccountsEnabled=service_accounts_enabled,
                standardFlowEnabled=standard_flow_enabled,
                attributes=attributes or {},
                defaultClientScopes=default_client_scopes,
                optionalClientScopes=optional_client_scopes,
                authorizationServicesEnabled=authorization_services_enabled,
                authorizationSettings=authorization_settings,
                rootUrl=root_url,
                bearerOnly=bearer_only if bearer_only is not None else False,
                fullScopeAllowed=full_scope_allowed if full_scope_allowed is not None else True,
                nodeReRegistrationTimeout=node_re_registration_timeout if node_re_registration_timeout is not None else 0,
                authenticationFlowBindingOverrides=authentication_flow_binding_overrides or {},
                frontchannelLogout=frontchannel_logout if frontchannel_logout is not None else False,
                consentRequired=consent_required if consent_required is not None else False,
                implicitFlowEnabled=implicit_flow_enabled if implicit_flow_enabled is not None else False,
                notBefore=not_before if not_before is not None else 0,
                enabled=enabled if enabled is not None else True,
                alwaysDisplayInConsole=always_display_in_console if always_display_in_console is not None else False,
                clientAuthenticatorType=client_authenticator_type or "client-secret",
                protocol=protocol,
                protocolMappers=pm_norm,

            )
        )
        return self

    def set_browser_security_headers(self, headers: Dict[str, str]) -> "RealmBuilder":
        self.realm.browserSecurityHeaders = headers
        return self

    # ----- Client scopes -----

    def add_client_scope(
        self,
        name: str,
        *,
        id: Optional[str] = None,
        description: Optional[str] = None,
        protocol: str = "openid-connect",
        attributes: Optional[Dict[str, Any]] = None,
        protocol_mappers: Optional[List[ProtocolMapperRepresentation]] = None,
    ) -> "RealmBuilder":
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
    ) -> "RealmBuilder":
        """No-op if a client scope with the same name already exists."""
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
        )

    def add_builtin_oidc_scopes(self) -> "RealmBuilder":
        """
        Ensure *non-duplicated* built-ins exist by name. We explicitly define
        `roles`, `email`, and `profile` below with custom mappers, so we do NOT
        create them here to avoid conflicts.
        """
        for n in ["web-origins", "address", "phone", "microprofile-jwt", "offline_access"]:
            self.ensure_client_scope(n, protocol="openid-connect")
        return self

    # ----- Groups -----

    def add_group(
        self,
        name: str,
        *,
        path: Optional[str] = None,
        realm_roles: Optional[List[str]] = None,
        client_roles: Optional[Dict[str, List[str]]] = None,
        attributes: Optional[Dict[str, List[str]]] = None,
        subgroups: Optional[List[GroupRepresentation]] = None,
    ) -> "RealmBuilder":
        self.realm.groups.append(
            GroupRepresentation(
                name=name,
                path=path,
                realmRoles=realm_roles,
                clientRoles=client_roles,
                attributes=attributes,
                subGroups=subgroups,
            )
        )
        return self

    # ----- Users -----

    def add_user(
        self,
        username: str,
        *,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        enabled: bool = True,
        totp: bool = True,
        email_verified: bool = False,
        password: Optional[str] = None,
        realm_roles: Optional[List[str]] = None,
        client_roles: Optional[Dict[str, List[str]]] = None,
        required_actions: Optional[List[str]] = None,
        attributes: Optional[Dict[str, Any]] = None,
        groups: Optional[List[str]] = None,
        service_account_client_id: Optional[str] = None,
    ) -> "RealmBuilder":
        creds = None
        if password:
            creds = [CredentialRepresentation(type="password", value=password, temporary=False)]
        self.realm.users.append(
            UserRepresentation(
                username=username,
                email=email,
                firstName=first_name,
                lastName=last_name,
                enabled=enabled,
                emailVerified=email_verified,
                credentials=creds,
                realmRoles=realm_roles,
                clientRoles=client_roles or {},
                requiredActions=required_actions or [],
                attributes=attributes,
                groups=groups or [],
                totp=totp,
                serviceAccountClientId=service_account_client_id,
            )
        )
        return self

    # ----- Finalize -----

    def build(self) -> RealmRepresentation:
        return self.realm


# ---------------------------------------------------------------------
# Assemble the test realm used by your tests/compose
# ---------------------------------------------------------------------

def osss_realm() -> RealmRepresentation:
    """
    Build the realm named "OSSS" used by CI/integration tests.
    Includes:
      - Essential realm roles
      - Two clients (`osss-api`, `admin-cli`)
      - Client scopes: roles, email, profile (with correct mappers)
      - Realm-level defaults so all clients receive those scopes
    """
    rb = RealmBuilder("OSSS", enabled=True)
    # Non-conflicting built-ins (we will explicitly define roles/email/profile next)
    rb.add_builtin_oidc_scopes()

    # --- Realm roles ---
    rb.add_realm_role("offline_access", "Offline Access", composite=False)
    rb.add_realm_role("uma_authorization", "UMA Authorization", composite=False)

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
        web_origins=["http://localhost:8081"],
        public_client=False,
        direct_access_grants_enabled=True,   # password grant
        service_accounts_enabled=True,
        standard_flow_enabled=True,          # authorization code flow
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
        default_client_scopes=["web-origins", "roles", "profile", "email"],
        optional_client_scopes=["address", "phone", "offline_access", "microprofile-jwt"],
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
        redirect_uris=["http://localhost:3000/*"],
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
        attributes={
            #"pkce.code.challenge.method": "S256",
            "post.logout.redirect.uris": "+"
        },
        default_client_scopes=[
            "profile",
            "email",
            "roles",
            "osss-api-audience"
        ],
        optional_client_scopes=["address", "phone", "offline_access", "microprofile-jwt"],
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
        default_client_scopes=["web-origins", "roles", "profile", "email", "roles"],
        optional_client_scopes=["address", "phone", "offline_access", "microprofile-jwt"],
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

    rb.add_client_role("osss-api", "api.user", description="Baseline access to OSSS API")
    rb.add_client_role("osss-api", "api.admin", description="Administrative access to OSSS API")
    rb.add_client_role(
        "osss-api",
        "api.teacher",
        description="Teacher access to OSSS API",
        attributes = {
            "allowed_schools": ["Heritage Elementary", "Oak View MS"],
            "grade_bands": ["6-8"],
            "scopes": ["students:read", "attendance:read", "roster:read"],
            "max_results": "1000",
        }
    )


    # --- Client scopes (define explicit mappers so tokens contain claims) ---

    # roles: realm + client roles into access/id/userinfo tokens
    rb.add_client_scope(
        name="roles",
        description="OIDC scope for realm & client roles",
        protocol="openid-connect",
        protocol_mappers=[
            ProtocolMapperRepresentation(
                name="realm roles",
                protocolMapper="oidc-usermodel-realm-role-mapper",
                config={
                    "multivalued": "true",
                    "userinfo.token.claim": "true",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "claim.name": "realm_access.roles",
                    "jsonType.label": "String",
                },
            ),
            ProtocolMapperRepresentation(
                name="client roles",
                protocolMapper="oidc-usermodel-client-role-mapper",
                config={
                    "multivalued": "true",
                    "userinfo.token.claim": "true",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "claim.name": "resource_access.${client_id}.roles",
                    "jsonType.label": "String",
                },
            )
        ],
    )

    # email: email + email_verified
    rb.add_client_scope(
        name="email",
        protocol="openid-connect",
        attributes={"include.in.token.scope": "true"},
        protocol_mappers=[
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
            ),
            ProtocolMapperRepresentation(
                name="email verified",
                protocolMapper="oidc-usermodel-property-mapper",
                config={
                    "userinfo.token.claim": "true",
                    "user.attribute": "emailVerified",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "claim.name": "email_verified",
                    "jsonType.label": "boolean",
                },
            ),
        ],
    )

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

    rb.add_user(
        username="admin@osss.local",
        email="admin@osss.local",
        enabled=True,
        email_verified=True,
        first_name="OSSS",
        last_name="Admin",
        totp=False,
        password="password",
        required_actions=[],
        realm_roles=["offline_access","uma_authorization","admin"],
        client_roles={
            "realm-management": ["realm-admin"],
            "account": ["manage-account", "view-profile"],
            "osss-api": ["admin"]
        },
        attributes={
            "department": ["IT"],
            "title": ["Administrator"],
        },
        groups=[  # optional; must exist in your realm tree
            # "/Admins"
        ],
        service_account_client_id=None,
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
        realm_roles=["uma_authorization"],
        client_roles={
            "account": ["view-profile"],
            "osss-api": ["api.user","api.teacher"],  # create a "user" role on your osss-api
        },
        attributes={"role": ["teacher"]},
    )

    # Realm-level defaults: ensure *every* client gets these
    rb.set_default_default_client_scopes(["roles", "web-origins", "profile", "email","roles"])
    rb.set_default_optional_client_scopes(["address", "phone", "offline_access", "microprofile-jwt"])

    return rb.build()


# ---------------------------------------------------------------------
# Build helpers + main
# ---------------------------------------------------------------------

def _norm_role_attrs(attrs: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    if not attrs:
        return out
    for k, v in attrs.items():
        if v is None:
            continue
        if isinstance(v, list):
            out[k] = [str(x) for x in v]
        else:
            out[k] = [str(v)]
    return out

def _ensure_roles_container(realm):
    """
    Make sure self.realm.roles has the shape:
      {
        "realm": [ RoleRepresentation, ... ],
        "client": { "<clientId>": [ RoleRepresentation, ... ] }
      }
    Works whether roles is a dict or a Pydantic model with .realm/.client.
    """
    roles = getattr(realm, "roles", None)
    if roles is None:
        realm.roles = {"realm": [], "client": {}}
        return

    # Pydantic model?
    if hasattr(roles, "realm") or hasattr(roles, "client"):
        if getattr(roles, "realm", None) is None:
            roles.realm = []
        if getattr(roles, "client", None) is None:
            roles.client = {}
        return

    # Plain dict
    if isinstance(roles, dict):
        roles.setdefault("realm", [])
        roles.setdefault("client", {})


def _dedupe(seq: Optional[List[str]]) -> List[str]:
    """Order-preserving de-duplication for small lists."""
    return list(dict.fromkeys(seq or []))


def build() -> RealmRepresentation:
    """
    Build realm and apply small normalizations:
      - De-dupe realm-level default scopes and client-level scope lists
      - De-dupe clientScopes by name
    """
    realm = osss_realm()

    # De-dupe realm default scope lists
    realm.defaultDefaultClientScopes = _dedupe(realm.defaultDefaultClientScopes)
    realm.defaultOptionalClientScopes = _dedupe(realm.defaultOptionalClientScopes)

    # De-dupe client-level scope lists
    for c in realm.clients:
        if c.defaultClientScopes is not None:
            c.defaultClientScopes = _dedupe(c.defaultClientScopes)
        if c.optionalClientScopes is not None:
            c.optionalClientScopes = _dedupe(c.optionalClientScopes)

    # Keep only unique clientScopes by name
    seen: set[str] = set()
    uniq: List[ClientScopeRepresentation] = []
    for cs in realm.clientScopes:
        if cs.name not in seen:
            seen.add(cs.name)
            uniq.append(cs)
    realm.clientScopes = uniq

    return realm


if __name__ == "__main__":
    # Build the realm
    realm = build()

    HERE = Path(__file__).resolve().parent
    OUT = HERE / "realm-export.json"


    payload = realm.model_dump(exclude_none=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(realm.model_dump(by_alias=True, exclude_none=True), f, indent=2)

    # Tiny summary on stdout
    print(f"✅ Wrote {OUT}")
    print(
        f"    clients={len(realm.clients)}  "
        f"clientScopes={len(realm.clientScopes)}  "
        f"realmRoles={len(realm.roles.realm)}  "
        f"users={len(realm.users)}"
    )
