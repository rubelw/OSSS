# superset_config.py
import os
from flask_appbuilder.security.manager import AUTH_OAUTH
from superset.security import SupersetSecurityManager

AUTH_TYPE = AUTH_OAUTH
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Gamma"
AUTH_ROLES_SYNC_AT_LOGIN = True

# Map Keycloak groups/roles to Superset roles
AUTH_ROLES_MAPPING = {
    "superset-a2a": ["Admin"],
    "superset-alpha": ["Alpha"],
    "superset-gamma": ["Gamma"],
    "superset-granter": ["Gamma", "sql_lab"],
}

# ----- Keycloak OIDC settings -----
# Base realm/issuer, no trailing slash
ISSUER = os.environ.get("KEYCLOAK_BASE_URL", "https://keycloak.local:8443/realms/OSSS").rstrip("/")

OAUTH_PROVIDERS = [
    {
        "name": "keycloak",
        "icon": "fa-address-card",
        "token_key": "access_token",
        "remote_app": {
            "client_id": os.environ.get("KEYCLOAK_CLIENT_ID", "superset"),
            "client_secret": os.environ.get("KEYCLOAK_CLIENT_SECRET", "password"),
            # Use OIDC discovery so Authlib obtains jwks_uri, userinfo, etc.
            "server_metadata_url": f"{ISSUER}/.well-known/openid-configuration",
            # Set the API base to the OIDC path so `get("userinfo")` is valid
            "api_base_url": f"{ISSUER}/protocol/openid-connect/",
            # You may keep these explicit; discovery will override if needed
            "authorize_url": f"{ISSUER}/protocol/openid-connect/auth",
            "access_token_url": f"{ISSUER}/protocol/openid-connect/token",
            "client_kwargs": {"scope": "openid email profile"},
        },
    },
]

class KeycloakSecurityManager(SupersetSecurityManager):
    def oauth_user_info(self, provider, response=None):
        if provider != "keycloak":
            return None

        # With api_base_url set to .../protocol/openid-connect/, this works:
        remote = self.appbuilder.sm.oauth_remotes[provider]
        me = remote.get("userinfo").json()

        username = me.get("preferred_username") or me.get("email")
        first_name = me.get("given_name") or ""
        last_name = me.get("family_name") or ""
        email = me.get("email") or f"{username}@example.com"

        groups = me.get("groups", []) or []
        # realm_roles = (me.get("realm_access") or {}).get("roles", [])
        # svc_roles = (me.get("resource_access") or {}).get("superset", {}).get("roles", [])

        return {
            "username": username,
            "name": me.get("name") or username,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "role_keys": groups,  # used with AUTH_ROLES_MAPPING
        }

CUSTOM_SECURITY_MANAGER = KeycloakSecurityManager

# Reverse proxy / gunicorn behind compose/nginx
ENABLE_PROXY_FIX = True

# Core app settings
SECRET_KEY = "please_change_me"
SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://osss:osss@postgres-superset:5432/superset"

# Optional: silence in-memory rate-limit warning if you have Redis
RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "")
