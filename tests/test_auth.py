from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("DISCORD_CLIENT_ID", "discord-client")
    monkeypatch.setenv("DISCORD_CLIENT_SECRET", "discord-secret")
    monkeypatch.setenv("DISCORD_REDIRECT_URI", "http://testserver/auth/callback")
    monkeypatch.setenv("FRONTEND_BASE_URL", "http://frontend.local")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://frontend.local")
    monkeypatch.setenv("ALLOWED_DISCORD_USER_IDS", "allowed-user")
    get_settings.cache_clear()

    with TestClient(create_app()) as test_client:
        yield test_client

    get_settings.cache_clear()


def complete_login(client: TestClient, monkeypatch, user_id: str):
    monkeypatch.setattr(
        "app.api.auth.requests.post",
        lambda *args, **kwargs: FakeResponse({"access_token": "discord-token"}),
    )
    monkeypatch.setattr(
        "app.api.auth.requests.get",
        lambda *args, **kwargs: FakeResponse(
            {
                "id": user_id,
                "username": "tester",
                "global_name": "Tester",
                "avatar": "abc123",
            }
        ),
    )

    login_response = client.get("/auth/login", follow_redirects=False)
    assert login_response.status_code == 302

    state = parse_qs(urlparse(login_response.headers["location"]).query)["state"][0]
    callback_response = client.get(f"/auth/callback?code=oauth-code&state={state}", follow_redirects=False)
    return callback_response


def test_allowlisted_user_can_login_and_persist_session(client, monkeypatch):
    callback_response = complete_login(client, monkeypatch, "allowed-user")

    assert callback_response.status_code == 302
    assert callback_response.headers["location"] == "http://frontend.local/app"

    me_response = client.get("/auth/me")
    payload = me_response.json()

    assert payload["authenticated"] is True
    assert payload["user"]["id"] == "allowed-user"
    assert payload["user"]["authorized"] is True


def test_non_allowlisted_user_is_logged_in_but_blocked(client, monkeypatch):
    callback_response = complete_login(client, monkeypatch, "blocked-user")

    assert callback_response.status_code == 302
    assert callback_response.headers["location"] == "http://frontend.local/login?error=not_allowed"

    me_response = client.get("/auth/me")
    payload = me_response.json()
    protected_response = client.get("/ltrc/status")

    assert payload["authenticated"] is True
    assert payload["user"]["authorized"] is False
    assert protected_response.status_code == 403


def test_logout_clears_session(client, monkeypatch):
    complete_login(client, monkeypatch, "allowed-user")

    logout_response = client.post("/auth/logout")
    me_response = client.get("/auth/me")

    assert logout_response.status_code == 200
    assert me_response.json() == {"authenticated": False, "user": None}


def test_protected_routes_require_authentication(client):
    response = client.get("/ltrc/status")

    assert response.status_code == 401
