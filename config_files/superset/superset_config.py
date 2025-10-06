from flask_appbuilder.security.manager import AUTH_OAUTH
from superset.security import SupersetSecurityManager
import os

AUTH_TYPE = AUTH_OAUTH
AUTH_USER_REGISTRATION = True
# Default role if no mapping matches (keep minimal)
AUTH_USER_REGISTRATION_ROLE = "Gamma"
# Keep roles synced with claims on every login
AUTH_ROLES_SYNC_AT_LOGIN = True

# Optional: map Keycloak groups (or roles) to Superset roles
# Keys are exact group/role strings from Keycloak token/userinfo
AUTH_ROLES_MAPPING = {
    "superset-admin": ["Admin"],
    "superset-alpha": ["Alpha"],
    "superset-gamma": ["Gamma"],
    "superset-granter": ["Gamma", "sql_lab"],
}

# OIDC / OAuth provider config (Authlib via FAB)
OAUTH_PROVIDERS = [
    {
        "name": "keycloak",
        "icon": "fa-address-card",
        "token_key": "access_token",  # where to find access token
        "remote_app": {
            # set these via env; we resolve here for clarity
            "client_id": os.environ.get("KEYCLOAK_CLIENT_ID", "superset"),
            "client_secret": os.environ.get("KEYCLOAK_CLIENT_SECRET", ""),
            # Your realm issuer base (no trailing slash)
            "api_base_url": os.environ.get("KEYCLOAK_BASE_URL", "https://keycloak.local:8443/realms/OSSS"),
            "access_token_url": os.environ.get("KEYCLOAK_TOKEN_URL", "https://keycloak.local:8443/realms/OSSS/protocol/openid-connect/token"),
            "authorize_url": os.environ.get("KEYCLOAK_AUTH_URL", "https://keycloak.local:8443/realms/OSSS/protocol/openid-connect/auth"),
            "client_kwargs": {"scope": "openid email profile"},
        },
    },
]

# Read groups/attrs from userinfo to build the user object & roles
class KeycloakSecurityManager(SupersetSecurityManager):
    def oauth_user_info(self, provider, response=None):
        if provider != "keycloak":
            return None
        # Authlib remote available as self.appbuilder.sm.oauth_remotes[provider]
        me = self.appbuilder.sm.oauth_remotes[provider].get("userinfo").json()

        # Username & name fields
        username = me.get("preferred_username") or me.get("email")
        first_name = me.get("given_name") or ""
        last_name = me.get("family_name") or ""
        email = me.get("email") or f"{username}@example.com"

        # Pull groups from userinfo (configure mapper in Keycloak)
        groups = me.get("groups", []) or []
        # You can also inspect realm/resource roles if you prefer:
        # realm_roles = (me.get("realm_access") or {}).get("roles", [])
        # svc_roles = (me.get("resource_access") or {}).get("superset", {}).get("roles", [])

        return {
            "username": username,
            "name": me.get("name") or username,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            # FAB uses 'role_keys' to apply AUTH_ROLES_MAPPING
            "role_keys": groups,
        }

CUSTOM_SECURITY_MANAGER = KeycloakSecurityManager

# If running behind reverse proxy (looks like you are)
ENABLE_PROXY_FIX = True

# config_files/superset/superset_config.py
SECRET_KEY = "please_change_me"  # any random string
SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://osss:osss@postgres-superset:5432/superset"

# Optional but nice:
ENABLE_PROXY_FIX = True
# Use Redis for rate-limit storage to silence in-memory warnings (db 1 reserved for limiter)
RATELIMIT_STORAGE_URI = "redis://superset_redis:6379/1"
