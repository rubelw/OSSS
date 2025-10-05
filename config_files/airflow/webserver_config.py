import os
from flask_appbuilder.security.manager import AUTH_OAUTH

AUTH_TYPE = AUTH_OAUTH
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Viewer"
AUTH_ROLES_SYNC_AT_LOGIN = True

KC_PUBLIC = os.getenv("KEYCLOAK_URL", "http://keycloak.local:8080")
KC_REALM  = os.getenv("KEYCLOAK_REALM", "OSSS")
BASE      = f"{KC_PUBLIC}/realms/{KC_REALM}/protocol/openid-connect"
DISCOVERY = f"{KC_PUBLIC}/realms/{KC_REALM}/.well-known/openid-configuration"

OAUTH_PROVIDERS = [{
    "name": "keycloak",
    "icon": "fa-key",
    "token_key": "access_token",
    "remote_app": {
        "client_id": os.getenv("KEYCLOAK_AIRFLOW_CLIENT_ID", "airflow"),
        "client_secret": os.getenv("KEYCLOAK_AIRFLOW_CLIENT_SECRET", "password"),
        "server_metadata_url": DISCOVERY,       # pulls jwks_uri, endpoints, etc.
        "api_base_url": BASE,                   # if any relative endpoint slips in, this fixes it
        "client_kwargs": {"scope": "openid email profile"},
    },
    "userinfo_endpoint": f"{BASE}/userinfo",    # absolute (via BASE)
}]

# Safety: if someone left a relative userinfo path, fix it to absolute at import time.
ui = OAUTH_PROVIDERS[0].get("userinfo_endpoint", "")
if not (ui.startswith("http://") or ui.startswith("https://")):
    OAUTH_PROVIDERS[0]["userinfo_endpoint"] = f"{BASE}/userinfo"

