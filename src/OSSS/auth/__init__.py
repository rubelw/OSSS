# src/OSSS/auth/__init__.py

# Public, current exports
from .deps import require_roles  # role-based route dependency

# Legacy exports that other modules may still import
try:
    from .dependencies import require_auth  # baseline auth dep used in older code/factories
except Exception as e:  # pragma: no cover
    # Provide a clear error if someone still imports require_auth but the module changed
    def require_auth(*_args, **_kwargs):
        raise RuntimeError("OSSS.auth.dependencies.require_auth is unavailable: " + str(e))

# Provide a backward-compatible _introspect symbol for old imports that expect it
try:
    from .introspection import introspect as _introspect  # preferred source
except Exception:
    # Fallback shim that explains configuration
    async def _introspect(*_args, **_kwargs):
        raise RuntimeError(
            "Keycloak token introspection is not configured. "
            "Set INTROSPECTION_CLIENT_ID/INTROSPECTION_CLIENT_SECRET or stop importing _introspect."
        )
