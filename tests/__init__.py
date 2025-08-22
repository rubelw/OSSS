# tests/__init__.py
# --------------------------------------------------------------------------------------
# Shared pytest utilities for this test package.
#
# Why this file exists:
# - Pytest will import package-level __init__.py files under the tests/ tree during
#   collection. Putting common fixtures here lets all tests in this package (and its
#   subpackages) use them without extra imports.
#
# What lives here:
# - A BaseOSSSClass that provides an `idp` fixture, which returns a ready-to-use
#   FastAPIKeycloak client pointed at the Keycloak instance started by tests/conftest.py.
#
# Pre-reqs for using the fixture:
# - Docker must be running.
# - `pytest` should be invoked so that tests/conftest.py brings up the Keycloak +
#   Postgres containers and waits for OIDC discovery (it handles the boot/wait loop).
# - If you run tests without that infra, any attempt to create the client below will
#   fail during OIDC discovery (HTTP 503 / connection refused).
#
# Import path note:
# - pytest.ini sets `pythonpath = src`, so `from src.OSSS import ...`
#   resolves to your local package code rather than an installed distribution.
# --------------------------------------------------------------------------------------

import pytest

from src.OSSS_bak import FastAPIKeycloak


class BaseOSSSClass:
    """
    Base class for test modules.

    Provides the `idp` fixture, which constructs a FastAPIKeycloak instance configured
    for the ephemeral test realm spun up by the docker-compose file
    (tests/keycloak_postgres.yaml).

    The realm and client credentials here MUST match what `build_realm.py` exports and
    what the container imports at startup. If you change secrets, client IDs, or the
    realm name there, keep the values below in sync.
    """

    @pytest.fixture
    def idp(self):
        """
        Return an authenticated client for the OSSS realm.

        server_url
          - We point to http://localhost:8085/auth to be compatible with legacy layouts.
            The FastAPIKeycloak constructor normalizes this: it strips a trailing `/auth`
            and will try both the modern and legacy OIDC discovery URLs internally.
            (So using either http://localhost:8085 or http://localhost:8085/auth works.)

        client_id / client_secret
          - Credentials for the `osss-api` defined in the exported realm. This client
            has direct access grants enabled in tests so password and refresh flows work.

        admin_client_secret
          - Secret for the `admin-cli` client. The fixture uses this to obtain an admin
            access token for admin endpoints (users/roles/groups).
          - In CI/dev we may skip strict “service-account must have realm-management roles”
            validation via an env var (e.g., KC_SKIP_ADMIN_ROLE_CHECK=1) to make tests less
            brittle. In a real environment you should grant appropriate service-account
            roles instead (e.g., realm-admin under Clients → realm-management).

        realm
          - Name of the test realm (“OSSS”) created by build_realm.py and imported by
            Keycloak at container startup.

        callback_uri
          - Redirect URI used by authorization-code flow tests. It only needs to match a
            value allowed in the `osss-api` config (wildcards are used in tests).

        If this fixture raises during creation, typical causes are:
          - Keycloak container not running or still booting.
          - Realm import failed (check docker logs for duplicate resource / DB errors).
          - Secrets or client IDs in this file don’t match the imported realm.
        """
        return FastAPIKeycloak(
            server_url="http://localhost:8085/auth",  # legacy-style; constructor normalizes
            client_id="osss-api",                  # must match realm-export.json
            client_secret="password",  # test-only secret
            admin_client_secret="password",  # admin-cli secret
            realm="OSSS",                              # test realm name
            callback_uri="http://localhost:8081/callback",  # allowed redirect in tests
        )
