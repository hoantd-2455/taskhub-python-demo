from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password, verify_password
from app.crud import refresh_tokens as refresh_token_crud
from app.crud import users as user_crud
from app.main import app
from app.models.enums import UserRole
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.user import UserUpdate


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_user() -> User:
    return User(
        id=4,
        email="auth@example.com",
        full_name="Authentication User",
        hashed_password=hash_password("correct-password"),
        role=UserRole.MEMBER,
        is_active=True,
        created_at=datetime(2026, 7, 22, tzinfo=timezone.utc),
    )


def test_register_hashes_password_and_hides_hash(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_user: User,
) -> None:
    captured_hashes: list[str] = []

    async def fake_get_user_by_email(_: object, __: str) -> None:
        return None

    async def fake_create_user(_: object, __: object, hashed_password: str) -> User:
        captured_hashes.append(hashed_password)
        return sample_user

    monkeypatch.setattr(user_crud, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(user_crud, "create_user", fake_create_user)

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "auth@example.com",
            "full_name": "Authentication User",
            "password": "correct-password",
        },
    )

    assert response.status_code == 201
    assert verify_password("correct-password", captured_hashes[0])
    assert "hashed_password" not in response.json()


def test_register_rejects_existing_email(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_user: User,
) -> None:
    async def fake_get_user_by_email(_: object, __: str) -> User:
        return sample_user

    monkeypatch.setattr(user_crud, "get_user_by_email", fake_get_user_by_email)

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "auth@example.com",
            "full_name": "Authentication User",
            "password": "correct-password",
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}


def test_login_issues_token_pair(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_user: User,
) -> None:
    async def fake_get_user_by_email(_: object, __: str) -> User:
        return sample_user

    async def fake_create_refresh_token(_: object, **__: object) -> RefreshToken:
        return RefreshToken(id=1, user_id=sample_user.id, jti="test-jti")

    monkeypatch.setattr(user_crud, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(refresh_token_crud, "create_refresh_token", fake_create_refresh_token)

    response = client.post(
        "/api/v1/auth/login",
        data={"username": sample_user.email, "password": "correct-password"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]
    assert response.json()["refresh_token"]


def test_login_rejects_incorrect_password(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_user: User,
) -> None:
    async def fake_get_user_by_email(_: object, __: str) -> User:
        return sample_user

    monkeypatch.setattr(user_crud, "get_user_by_email", fake_get_user_by_email)

    response = client.post(
        "/api/v1/auth/login",
        data={"username": sample_user.email, "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect email or password"}


def test_me_requires_a_valid_access_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_user: User,
) -> None:
    async def fake_get_user_by_id(_: object, __: int) -> User:
        return sample_user

    monkeypatch.setattr(user_crud, "get_user_by_id", fake_get_user_by_id)

    missing_token = client.get("/api/v1/users/me")
    valid_token = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {create_access_token(sample_user.id)}"},
    )
    refresh_token_as_access = client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer not-a-token"},
    )

    assert missing_token.status_code == 401
    assert valid_token.status_code == 200
    assert valid_token.json()["id"] == sample_user.id
    assert "hashed_password" not in valid_token.json()
    assert refresh_token_as_access.status_code == 401


def test_update_me_only_uses_submitted_fields(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_user: User,
) -> None:
    async def fake_get_user_by_id(_: object, __: int) -> User:
        return sample_user

    async def fake_update_user(_: object, user: User, user_in: UserUpdate) -> User:
        assert user_in.full_name is not None
        user.full_name = user_in.full_name
        return user

    monkeypatch.setattr(user_crud, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(user_crud, "update_user", fake_update_user)

    response = client.patch(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {create_access_token(sample_user.id)}"},
        json={"full_name": "Updated Name"},
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"
    assert response.json()["email"] == "auth@example.com"


def test_refresh_rotates_token_and_logout_revokes_it(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_user: User,
) -> None:
    from app.core.security import create_refresh_token

    token, jti, _ = create_refresh_token(sample_user.id)
    stored_token = RefreshToken(id=2, user_id=sample_user.id, jti=jti)
    revoked_tokens: list[RefreshToken] = []
    active_tokens = {jti: stored_token}

    async def fake_get_active_refresh_token(_: object, requested_jti: str) -> RefreshToken | None:
        return active_tokens.get(requested_jti)

    async def fake_get_user_by_id(_: object, __: int) -> User:
        return sample_user

    async def fake_revoke_refresh_token(_: object, refresh_token: RefreshToken) -> None:
        revoked_tokens.append(refresh_token)
        active_tokens.pop(refresh_token.jti)

    async def fake_rotate_refresh_token(
        _: object,
        current_token: RefreshToken,
        **kwargs: object,
    ) -> RefreshToken:
        active_tokens.pop(current_token.jti)
        replacement = RefreshToken(id=3, user_id=sample_user.id, jti=str(kwargs["jti"]))
        active_tokens[replacement.jti] = replacement
        return replacement

    monkeypatch.setattr(
        refresh_token_crud,
        "get_active_refresh_token",
        fake_get_active_refresh_token,
    )
    monkeypatch.setattr(refresh_token_crud, "revoke_refresh_token", fake_revoke_refresh_token)
    monkeypatch.setattr(refresh_token_crud, "rotate_refresh_token", fake_rotate_refresh_token)
    monkeypatch.setattr(user_crud, "get_user_by_id", fake_get_user_by_id)

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    logged_out = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refreshed.json()["refresh_token"]},
    )
    revoked = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refreshed.json()["refresh_token"]},
    )

    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != token
    assert logged_out.status_code == 204
    assert revoked.status_code == 401
    assert len(revoked_tokens) == 1


def test_change_password_checks_current_password_and_revokes_sessions(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_user: User,
) -> None:
    changed_hashes: list[str] = []

    async def fake_get_user_by_id(_: object, __: int) -> User:
        return sample_user

    async def fake_change_password(_: object, __: User, hashed_password: str) -> User:
        changed_hashes.append(hashed_password)
        return sample_user

    monkeypatch.setattr(user_crud, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(user_crud, "change_password", fake_change_password)
    headers = {"Authorization": f"Bearer {create_access_token(sample_user.id)}"}

    incorrect = client.post(
        "/api/v1/users/me/change-password",
        headers=headers,
        json={"current_password": "wrong-password", "new_password": "new-password"},
    )
    changed = client.post(
        "/api/v1/users/me/change-password",
        headers=headers,
        json={"current_password": "correct-password", "new_password": "new-password"},
    )

    assert incorrect.status_code == 400
    assert changed.status_code == 204
    assert verify_password("new-password", changed_hashes[0])
