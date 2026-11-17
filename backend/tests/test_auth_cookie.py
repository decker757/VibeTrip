from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import backend.auth
from backend.main import app


def _signup_cookie_header(monkeypatch, tmp_path) -> str:
    monkeypatch.setattr(backend.auth, "AUTH_FILE", tmp_path / "auth_users.json")
    client = TestClient(app)
    response = client.post(
        "/auth/signup",
        json={"email": f"cookie-{uuid4().hex[:8]}@example.com", "password": "correct-horse-battery"},
    )
    assert response.status_code == 200, response.text
    return response.headers["set-cookie"].lower()


def test_session_cookie_is_not_secure_by_default_for_local_http(monkeypatch, tmp_path):
    monkeypatch.delenv("VIBETRIP_COOKIE_SECURE", raising=False)
    header = _signup_cookie_header(monkeypatch, tmp_path)
    assert "httponly" in header
    assert "secure" not in header


@pytest.mark.parametrize("value", ["true", "1", "yes"])
def test_session_cookie_is_secure_when_deployed_over_https(monkeypatch, tmp_path, value):
    monkeypatch.setenv("VIBETRIP_COOKIE_SECURE", value)
    header = _signup_cookie_header(monkeypatch, tmp_path)
    assert "secure" in header
    assert "samesite=lax" in header


def test_logout_clears_the_secure_session_and_me_is_unauthorised(monkeypatch, tmp_path):
    monkeypatch.setenv("VIBETRIP_COOKIE_SECURE", "true")
    monkeypatch.setattr(backend.auth, "AUTH_FILE", tmp_path / "auth_users.json")
    client = TestClient(app, base_url="https://testserver")
    signup = client.post(
        "/auth/signup",
        json={"email": f"logout-{uuid4().hex[:8]}@example.com", "password": "correct-horse-battery"},
    )
    assert signup.status_code == 200
    assert client.get("/auth/me").status_code == 200

    logout = client.post("/auth/logout")
    header = logout.headers["set-cookie"].lower()
    assert "max-age=0" in header and "secure" in header
    assert client.get("/auth/me").status_code == 401
