# tests/app.py
# -------------------------------------------------------------------------------------------------
# Minimal FastAPI app used during local testing / manual verification.
#
# Why this file exists
# --------------------
# Some test suites (or developers) prefer to hit a running HTTP API instead of calling the
# Python client directly. This app wires our FastAPIKeycloak helper into a tiny REST surface
# that mirrors common admin and user flows against a Keycloak realm spun up by the test
# docker-compose (see tests/keycloak_postgres.yaml) and data exported by build_realm.py.
#
# How to run locally
# ------------------
# 1) Start the test Keycloak stack (the pytest conftest does this automatically):
#      docker compose -f tests/keycloak_postgres.yaml up -d
#    Wait until OIDC discovery is available at:
#      http://localhost:8085/realms/OSSS/.well-known/openid-configuration
#
# 2) Launch this app:
#      uvicorn app:app --reload --port 8081
#
# 3) Open Swagger UI:
#      http://127.0.0.1:8081/docs
#
# Security / secrets
# ------------------
# - Client/realm secrets here are test-only and must match the realm-export created by
#   build_realm.py. Do NOT reuse in production.
# - The admin service-account must have sufficient realm-management roles to call admin APIs.
#   (In CI you may disable strict checks via KC_SKIP_ADMIN_ROLE_CHECK=1.)
# -------------------------------------------------------------------------------------------------

from typing import List, Optional

import uvicorn
from fastapi import FastAPI, Depends, Query, Body, Request
from fastapi.responses import JSONResponse
from pydantic import SecretStr

# FastAPIKeycloak is the integration wrapper; the models/enums come from the same package.
from src.OSSS_bak import (
    FastAPIKeycloak,
    HTTPMethod,
    KeycloakUser,
    OIDCUser,
    UsernamePassword,
    KeycloakError,
)

# Create the FastAPI app instance.
app = FastAPI()

# Instantiate the Keycloak helper.
# Note on `server_url`:
# - We pass the base Keycloak URL *without* `/auth`. The library normalizes both modern
#   (no `/auth`) and legacy (with `/auth`) deployments and tries both discovery URLs.
idp = FastAPIKeycloak(
    server_url="http://localhost:8085",   # test Keycloak container base URL (no /auth)
    realm="OSSS",                         # realm name created by build_realm.py
    client_id="osss-api",              # must match the exported realm client
    client_secret="password",  # test-only client secret
    admin_client_secret="password",  # admin-cli service account secret
    callback_uri="http://localhost:8081/callback",     # allowed redirect in test realm
    # If you need to override discovery explicitly, you could pass a well-known URL here.
    # well_known_endpoint="http://localhost:8085/realms/OSSS/.well-known/openid-configuration"
)

# Inject OAuth client config into Swagger UI so you can try interactive flows.
idp.add_swagger_config(app)


# -------------------------------
# Error handling
# -------------------------------

# Convert our library’s KeycloakError into a structured JSON response for FastAPI.
@app.exception_handler(KeycloakError)
async def keycloak_exception_handler(request: Request, exc: KeycloakError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.reason},
    )


# -------------------------------
# Admin (dangerous; test-only)
# -------------------------------
# These endpoints proxy requests as the admin service account. Do not expose in production.

@app.post("/proxy", tags=["admin-cli"])
def proxy_admin_request(
    relative_path: str,
    method: HTTPMethod,
    additional_headers: dict = Body(None),
    payload: dict = Body(None),
):
    """
    Raw admin proxy to Keycloak. Example:
      POST /proxy?relative_path=/admin/realms/OSSS/users&method=GET
    Only for troubleshooting in a local/test environment.
    """
    return idp.proxy(
        additional_headers=additional_headers,
        relative_path=relative_path,
        method=method,
        payload=payload,
    )


@app.get("/identity-providers", tags=["admin-cli"])
def get_identity_providers():
    """List configured identity providers for the realm."""
    return idp.get_identity_providers()


@app.get("/idp-configuration", tags=["admin-cli"])
def get_idp_config():
    """Expose the realm’s OpenID Provider configuration (discovery doc)."""
    return idp.open_id_configuration


# -------------------------------
# User Management
# -------------------------------

@app.get("/users", tags=["user-management"])
def get_users():
    """Return all users in the realm (admin privileges required)."""
    return idp.get_all_users()


@app.get("/user", tags=["user-management"])
def get_user_by_query(query: str = None):
    """
    Lookup a user by a Keycloak-native query string, e.g.:
      /user?query=username=alice  or  /user?query=email=alice@example.com
    """
    return idp.get_user(query=query)


@app.post("/users", tags=["user-management"])
def create_user(
    first_name: str, last_name: str, email: str, password: SecretStr, id: str = None
):
    """
    Create a user with a password. For convenience, we use the email as the username.
    The SecretStr ensures the password isn’t logged by FastAPI.
    """
    return idp.create_user(
        first_name=first_name,
        last_name=last_name,
        username=email,
        email=email,
        password=password.get_secret_value(),
        id=id,
    )


@app.get("/user/{user_id}", tags=["user-management"])
def get_user(user_id: str = None):
    """Fetch a single user by ID."""
    return idp.get_user(user_id=user_id)


@app.put("/user", tags=["user-management"])
def update_user(user: KeycloakUser):
    """
    Update a user (you must send the full object).
    Keycloak treats required-actions and attributes as part of the user payload.
    """
    return idp.update_user(user=user)


@app.delete("/user/{user_id}", tags=["user-management"])
def delete_user(user_id: str):
    """Delete the user with the given ID."""
    return idp.delete_user(user_id=user_id)


@app.put("/user/{user_id}/change-password", tags=["user-management"])
def change_password(user_id: str, new_password: SecretStr):
    """Set (or reset) the user’s password."""
    return idp.change_password(user_id=user_id, new_password=new_password)


@app.put("/user/{user_id}/send-email-verification", tags=["user-management"])
def send_email_verification(user_id: str):
    """Send the built-in Keycloak email verification mail for a user."""
    return idp.send_email_verification(user_id=user_id)


# -------------------------------
# Role Management (realm roles)
# -------------------------------

@app.get("/roles", tags=["role-management"])
def get_all_roles():
    """List all realm roles."""
    return idp.get_all_roles()


@app.get("/role/{role_name}", tags=["role-management"])
def get_role(role_name: str):
    """Get a specific realm role by name."""
    return idp.get_roles([role_name])


@app.post("/roles", tags=["role-management"])
def add_role(role_name: str):
    """Create a new realm role."""
    return idp.create_role(role_name=role_name)


@app.delete("/roles", tags=["role-management"])
def delete_roles(role_name: str):
    """Delete a realm role by name."""
    return idp.delete_role(role_name=role_name)


# -------------------------------
# Group Management
# -------------------------------

@app.get("/groups", tags=["group-management"])
def get_all_groups():
    """List top-level groups for the realm."""
    return idp.get_all_groups()


@app.get("/group/{group_name}", tags=["group-management"])
def get_group(group_name: str):
    """Fetch group objects by name (top-level only)."""
    return idp.get_groups([group_name])


@app.get("/group-by-path/{path: path}", tags=["group-management"])
def get_group_by_path(path: str):
    """
    Fetch a group by its full path (e.g. /parent/child).
    NOTE: The path converter here is written as `{path: path}` to mirror the original test code.
    """
    return idp.get_group_by_path(path)


@app.post("/groups", tags=["group-management"])
def add_group(group_name: str, parent_id: Optional[str] = None):
    """Create a new group, optionally under a parent group."""
    return idp.create_group(group_name=group_name, parent=parent_id)


@app.delete("/groups", tags=["group-management"])
def delete_groups(group_id: str):
    """Delete a group by ID."""
    return idp.delete_group(group_id=group_id)


# -------------------------------
# User ↔ Role assignments
# -------------------------------

@app.post("/users/{user_id}/roles", tags=["user-roles"])
def add_roles_to_user(user_id: str, roles: Optional[List[str]] = Query(None)):
    """Assign one or more realm roles to a user."""
    return idp.add_user_roles(user_id=user_id, roles=roles)


@app.get("/users/{user_id}/roles", tags=["user-roles"])
def get_user_roles(user_id: str):
    """List realm roles currently assigned to a user."""
    return idp.get_user_roles(user_id=user_id)


@app.delete("/users/{user_id}/roles", tags=["user-roles"])
def delete_roles_from_user(user_id: str, roles: Optional[List[str]] = Query(None)):
    """Remove one or more realm roles from a user."""
    return idp.remove_user_roles(user_id=user_id, roles=roles)


# -------------------------------
# User ↔ Group memberships
# -------------------------------

@app.post("/users/{user_id}/groups", tags=["user-groups"])
def add_group_to_user(user_id: str, group_id: str):
    """Add the user to a group."""
    return idp.add_user_group(user_id=user_id, group_id=group_id)


@app.get("/users/{user_id}/groups", tags=["user-groups"])
def get_user_groups(user_id: str):
    """List the groups the user belongs to."""
    return idp.get_user_groups(user_id=user_id)


@app.delete("/users/{user_id}/groups", tags=["user-groups"])
def delete_groups_from_user(user_id: str, group_id: str):
    """Remove the user from a group."""
    return idp.remove_user_group(user_id=user_id, group_id=group_id)


# -------------------------------
# Example “protected” user flows
# -------------------------------

@app.get("/protected", tags=["example-user-request"])
def protected(user: OIDCUser = Depends(idp.get_current_user())):
    """
    Return the decoded OIDC user for a valid access token.
    - Pass the token as `Authorization: Bearer <access_token>`
    - Uses the library’s dependency that validates signature, exp, audience (account).
    """
    return user


@app.get("/current_user/roles", tags=["example-user-request"])
def get_current_users_roles(user: OIDCUser = Depends(idp.get_current_user())):
    """
    Convenience endpoint to read roles from the access token.
    Requires the ‘roles’ client scope and role mappers to be present in the realm.
    """
    return user.roles


@app.get("/admin", tags=["example-user-request"])
def company_admin(
    user: OIDCUser = Depends(idp.get_current_user(required_roles=["admin"])),
):
    """
    Example of role-gated access. Only tokens that include the 'admin' role will pass.
    """
    return f"Hi admin {user}"


@app.post("/login", tags=["example-user-request"])
def login(user: UsernamePassword = Body(...)):
    """
    Resource-owner password credentials (ROPC) flow for test/dev.
    - Works only because `osss-api` has Direct Access Grants enabled.
    - Not recommended for production; prefer Authorization Code + PKCE for browser apps.
    """
    return idp.user_login(
        username=user.username, password=user.password.get_secret_value()
    )


# -------------------------------
# Auth Code flow helpers
# -------------------------------

@app.get("/login-link", tags=["auth-flow"])
def login_redirect():
    """Return the authorization endpoint URL for browser-based login."""
    return idp.login_uri


@app.get("/callback", tags=["auth-flow"])
def callback(session_state: str, code: str):
    """
    Authorization Code callback: exchange the `code` for tokens.
    The `callback_uri` above must match the client’s configured redirect URI.
    """
    return idp.exchange_authorization_code(session_state=session_state, code=code)


@app.get("/logout", tags=["auth-flow"])
def logout():
    """Return the realm’s end-session URL (front-channel logout)."""
    return idp.logout_uri


# Standard uvicorn entry point for quick local runs.
if __name__ == "__main__":
    # Use 127.0.0.1 rather than 0.0.0.0 for a dev-only binding. Change as needed.
    uvicorn.run("app:app", host="127.0.0.1", port=8081)
