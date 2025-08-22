# tests/test_functional.py
# ----------------------------------------------------------------------------------------------------
# Functional tests that exercise a running Keycloak (started by tests/conftest.py) through the
# FastAPIKeycloak wrapper. These tests validate end-to-end behavior:
#   • User lifecycle (create, lookup, delete)
#   • Realm role lifecycle (create, assign to users, remove, delete)
#   • Group lifecycle (create top-level and nested groups, lookup by path, delete)
#   • Authentication/token flows (password grant, current user dependency)
#   • Required-action login failures (e.g., CONFIGURE_TOTP) and recovery
#
# IMPORTANT:
# - These tests assume a fresh realm defined by tests/realm-export.json and a running Keycloak.
# - The infra is brought up by tests/conftest.py (docker compose) and waited on before collection.
# - TEST_PASSWORD is intentionally static for repeatability across runs.
# ----------------------------------------------------------------------------------------------------

from typing import List

import pytest as pytest
from fastapi import HTTPException

from src.OSSS_bak import KeycloakError
from src.OSSS_bak.exceptions import (
    ConfigureTOTPException,
    UpdatePasswordException,
    UpdateProfileException,
    UpdateUserLocaleException,
    UserNotFound,
    VerifyEmailException,
)
from src.OSSS_bak import (
    KeycloakGroup,
    KeycloakRole,
    KeycloakToken,
    KeycloakUser,
    OIDCUser,
)
from tests import BaseOSSSClass

# Shared password for test users. Chosen to be simple and predictable for fixtures.
TEST_PASSWORD = "test-password"


class TestAPIFunctional(BaseOSSSClass):
    """
    Functional integration tests for Keycloak operations against a live container.

    This class inherits the `idp` fixture from tests/__init__.py (BaseOSSSClass) which creates a
    FastAPIKeycloak instance configured to talk to the local Keycloak started by conftest.py.
    """

    @pytest.fixture
    def user(self, idp):
        """
        Create a single user that many tests can share.

        The user is created with:
          - email == username (simplifies lookups)
          - email verification disabled (to avoid out-of-band flows)
          - a fixed password (TEST_PASSWORD)

        NOTE: Tests that modify this user (e.g., add required actions) must clean up after themselves.
        """
        return idp.create_user(
            first_name="test",
            last_name="user",
            username="user@code-specialist.com",
            email="user@code-specialist.com",
            password=TEST_PASSWORD,
            enabled=True,
            send_email_verification=False,
        )

    @pytest.fixture()
    def users(self, idp):
        """
        Create two distinct users (Alice and Bob) and verify Keycloak’s duplicate handling.

        The flow:
          1) Assert that the realm has no users to start (fresh import).
          2) Create Alice, assert she appears in the list.
          3) Attempt to create Alice again; expect a KeycloakError (HTTP 409 from Keycloak).
          4) Create Bob, assert there are exactly two users.

        Returns:
            tuple[KeycloakUser, KeycloakUser]: (alice, bob)
        """
        # Sanity: with our test realm, we should start empty.
        assert idp.get_all_users() == []  # Start with empty user list

        # Create User A (Alice)
        user_alice = idp.create_user(
            first_name="test",
            last_name="user",
            username="testuser_alice@code-specialist.com",
            email="testuser_alice@code-specialist.com",
            password=TEST_PASSWORD,
            enabled=True,
            send_email_verification=False,
        )
        assert isinstance(user_alice, KeycloakUser)
        assert len(idp.get_all_users()) == 1

        # Attempt duplicate creation → should raise error (Keycloak 409)
        with pytest.raises(KeycloakError):
            idp.create_user(
                first_name="test",
                last_name="user",
                username="testuser_alice@code-specialist.com",
                email="testuser_alice@code-specialist.com",
                password=TEST_PASSWORD,
                enabled=True,
                send_email_verification=False,
            )
        assert len(idp.get_all_users()) == 1

        # Create User B (Bob)
        user_bob = idp.create_user(
            first_name="test",
            last_name="user",
            username="testuser_bob@code-specialist.com",
            email="testuser_bob@code-specialist.com",
            password=TEST_PASSWORD,
            enabled=True,
            send_email_verification=False,
        )
        assert isinstance(user_bob, KeycloakUser)
        assert len(idp.get_all_users()) == 2

        return user_alice, user_bob

    def test_roles(self, idp, users):
        """
        Validate the role lifecycle and role enforcement on tokens.

        Steps:
          - Each new user should have exactly one default realm role: 'default-roles-test'.
          - The realm initially has three realm roles: default-roles-test, offline_access, uma_authorization.
          - Create two custom roles, assign them to users, confirm via `get_user_roles`.
          - Acquire tokens for the users and verify role-gated access using `get_current_user(required_roles=[...])`.
          - Remove roles and clean up (delete roles and users).
        """
        user_alice, user_bob = users

        # Default role checks for Alice and Bob: both should only have 'default-roles-test'
        user_alice_roles = idp.get_user_roles(user_id=user_alice.id)
        assert len(user_alice_roles) == 1
        for role in user_alice_roles:
            assert role.name in ["default-roles-test"]

        user_bob_roles = idp.get_user_roles(user_id=user_bob.id)
        assert len(user_bob_roles) == 1
        for role in user_bob_roles:
            assert role.name in ["default-roles-test"]

        # Realm default roles (from our realm export)
        all_roles = idp.get_all_roles()
        assert len(all_roles) == 3
        for role in all_roles:
            assert role.name in [
                "default-roles-test",
                "offline_access",
                "uma_authorization",
            ]

        # Create two new roles
        test_role_saturn = idp.create_role("test_role_saturn")
        test_role_mars = idp.create_role("test_role_mars")
        all_roles = idp.get_all_roles()
        assert len(all_roles) == 5

        # Assign Saturn to Alice → she should now have 2 roles
        idp.add_user_roles(user_id=user_alice.id, roles=[test_role_saturn.name])
        user_alice_roles = idp.get_user_roles(user_id=user_alice.id)
        assert len(user_alice_roles) == 2

        # Assign Saturn + Mars to Bob → he should now have 3 roles
        idp.add_user_roles(
            user_id=user_bob.id, roles=[test_role_saturn.name, test_role_mars.name]
        )
        user_bob_roles = idp.get_user_roles(user_id=user_bob.id)
        assert len(user_bob_roles) == 3

        # Password-grant login for both users → validate access tokens are well-formed
        keycloak_token_alice = idp.user_login(
            username=user_alice.username, password=TEST_PASSWORD
        )
        assert idp.token_is_valid(keycloak_token_alice.access_token)

        keycloak_token_bob = idp.user_login(
            username=user_bob.username, password=TEST_PASSWORD
        )
        assert idp.token_is_valid(keycloak_token_bob.access_token)

        # Use the dependency generator directly to parse/validate a JWT and enrich with roles
        current_user_function = idp.get_current_user()
        current_user = current_user_function(token=keycloak_token_alice.access_token)
        assert current_user.sub == user_alice.id  # subject must match user id

        # Role-gated access:
        # Alice does NOT have Mars → expect HTTP 403 from dependency
        current_user_function = idp.get_current_user(required_roles=[test_role_mars.name])
        with pytest.raises(HTTPException):
            current_user_function(token=keycloak_token_alice.access_token)

        # Bob DOES have Mars → must pass
        current_user = current_user_function(token=keycloak_token_bob.access_token)
        assert current_user.sub == user_bob.id

        # Remove Mars from Bob → expect his role count to drop by 1
        idp.remove_user_roles(user_id=user_bob.id, roles=[test_role_mars.name])
        user_bob_roles = idp.get_user_roles(user_id=user_bob.id)
        assert len(user_bob_roles) == 2

        # Cleanup: delete newly created roles and users
        idp.delete_role(role_name=test_role_saturn.name)
        idp.delete_role(role_name=test_role_mars.name)
        idp.delete_user(user_id=user_alice.id)
        idp.delete_user(user_id=user_bob.id)

    def test_user_with_initial_roles(self, idp):
        """
        Create a user with initial roles and verify the roles are emitted in the user’s access token.

        Flow:
          - Create two realm roles (role_a, role_b).
          - Create user with `initial_roles=["role_a","role_b"]`.
          - Perform a password-grant login and decode the token to an OIDCUser.
          - Assert both roles are present.
          - Cleanup roles and user.
        """
        idp.create_role("role_a")
        idp.create_role("role_b")

        user = idp.create_user(
            first_name="test",
            last_name="user",
            username="user@code-specialist.com",
            email="user@code-specialist.com",
            initial_roles=["role_a", "role_b"],
            password=TEST_PASSWORD,
            enabled=True,
            send_email_verification=False,
        )

        # Confirm roles appear in user’s token
        user_token = idp.user_login(username=user.username, password=TEST_PASSWORD)
        # Validate/parse the JWT with the "account" audience so the model has the right fields
        decoded_token = idp._decode_token(token=user_token.access_token, audience="account")
        oidc_user = OIDCUser.model_validate(decoded_token)
        for role in ["role_a", "role_b"]:
            assert role in oidc_user.roles

        # Clean up realm state to keep other tests isolated
        idp.delete_role("role_a")
        idp.delete_role("role_b")
        idp.delete_user(user.id)

    def test_groups(self, idp):
        """
        Validate group creation, nesting, and path lookups.

        Steps:
          - Negative cases: creating/getting with invalid params should raise KeycloakError.
          - Create two top-level groups (Foo/Bar) → expect 2 total.
          - Under Foo, create nested subgroups (L2/L3/L4).
          - Lookup Foo by path and verify its direct children count.
          - Lookup a deeper subgroup by path and assert it resolves.
          - Delete top-level groups to clean up.
        """
        # Invalid group ops should raise errors
        with pytest.raises(KeycloakError):
            idp.create_group(group_name=None)

        with pytest.raises(KeycloakError):
            idp.get_group(group_id=None)

        foo_group = idp.create_group(group_name="Foo Group")
        bar_group = idp.create_group(group_name="Bar Group")

        all_groups = idp.get_all_groups()
        assert len(all_groups) == 2

        # Create nested subgroups under Foo (mix object and id parents on purpose)
        subgroup1 = idp.create_group(group_name="Subgroup 01", parent=foo_group)
        subgroup2 = idp.create_group(group_name="Subgroup 02", parent=foo_group.id)
        subgroup_l3 = idp.create_group(group_name="Subgroup l3", parent=subgroup2)
        subgroup_l4 = idp.create_group(group_name="Subgroup l4", parent=subgroup_l3)

        # Lookup groups by path and ensure the FastAPIKeycloak helper populates subGroups
        foo_group = idp.get_group_by_path(foo_group.path)
        assert foo_group and len(foo_group.subGroups) == 2

        subgroup_by_path = idp.get_group_by_path(subgroup2.path)
        assert subgroup_by_path.id == subgroup2.id

        # Cleanup top-level groups (deletes subtree as well)
        idp.delete_group(bar_group.id)
        idp.delete_group(foo_group.id)

    def test_user_groups(self, idp, user):
        """
        Assign and remove a user from a group and confirm membership changes are reflected.

        Flow:
          - Create a group Foo.
          - Add user to Foo and verify a single membership is returned.
          - Remove membership and verify it’s empty again.
          - Cleanup (delete group and user).
        """
        foo_group = idp.create_group(group_name="Foo")
        idp.add_user_group(user_id=user.id, group_id=foo_group.id)

        user_groups = idp.get_user_groups(user.id)
        assert len(user_groups) == 1

        idp.remove_user_group(user.id, foo_group.id)
        assert len(idp.get_user_groups(user.id)) == 0

        # Cleanup
        idp.delete_group(foo_group.id)
        idp.delete_user(user.id)

    @pytest.mark.parametrize(
        "action, exception",
        [
            ("update_user_locale", UpdateUserLocaleException),
            ("CONFIGURE_TOTP", ConfigureTOTPException),
            ("VERIFY_EMAIL", VerifyEmailException),
            ("UPDATE_PASSWORD", UpdatePasswordException),
            ("UPDATE_PROFILE", UpdateProfileException),
        ],
    )
    def test_login_exceptions(self, idp, action, exception, user):
        """
        Verify that required actions block login with the expected exception, and
        that removing the required action restores successful login.

        For each (action, expected_exception):
          - Perform a successful login to ensure baseline works.
          - Add the required action to the user and update it in Keycloak.
          - Attempt login → expect the mapped exception.
          - Remove the required action and update the user again.
          - Confirm login succeeds.
          - Cleanup (delete user).
        """
        tokens = idp.user_login(username=user.username, password=TEST_PASSWORD)
        assert tokens.access_token

        # Add required action → login should fail with the mapped exception
        user.requiredActions.append(action)
        user = idp.update_user(user=user)
        with pytest.raises(exception):
            idp.user_login(username=user.username, password=TEST_PASSWORD)

        # Remove required action → login should succeed again
        user.requiredActions.remove(action)
        user = idp.update_user(user=user)
        assert idp.user_login(username=user.username, password=TEST_PASSWORD)

        # Cleanup
        idp.delete_user(user.id)

    def test_user_not_found_exception(self, idp):
        """
        Ensure the wrapper raises `UserNotFound` in both lookup styles:
          - direct by user_id
          - filtered search via query string
        """
        with pytest.raises(UserNotFound):
            idp.get_user(user_id='abc')

        with pytest.raises(UserNotFound):
            idp.get_user(query='username="some_non_existant_username"')
