"""Self-contained local authentication for the hackathon MVP.

Users are persisted in a private JSON file so judges do not need to configure a
hosted auth provider. Passwords use scrypt and sessions use signed HS256-style
tokens in an HttpOnly cookie. Replace this adapter with a managed identity
provider before production deployment.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, Request


AUTH_FILE = Path(os.getenv("VIBETRIP_AUTH_FILE", Path(__file__).with_name("auth_users.json")))
AUTH_SECRET = os.getenv("VIBETRIP_AUTH_SECRET", "vibetrip-local-development-secret")
SESSION_COOKIE = "vibetrip_session"
SESSION_SECONDS = 60 * 60 * 24 * 7


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${_encode(salt)}${_encode(digest)}"


def _password_matches(password: str, stored: str) -> bool:
    try:
        algorithm, encoded_salt, encoded_digest = stored.split("$", 2)
        if algorithm != "scrypt":
            return False
        candidate = _password_hash(password, _decode(encoded_salt)).split("$", 2)[2]
        return hmac.compare_digest(candidate, encoded_digest)
    except (ValueError, TypeError):
        return False


def _load_users() -> dict[str, dict[str, Any]]:
    try:
        return json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_users(users: dict[str, dict[str, Any]]) -> None:
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = AUTH_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(users, indent=2), encoding="utf-8")
    temporary.replace(AUTH_FILE)


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {key: user[key] for key in ("id", "email", "display_name", "home_base")}


class LocalAuthRepository:
    def __init__(self) -> None:
        self.users = _load_users()
        if not self.users:
            demo = {
                "id": "demo-user",
                "email": "demo@vibetrip.local",
                "display_name": "Ernest Tan",
                "home_base": "Singapore",
                "password_hash": _password_hash("vibetrip-demo"),
            }
            self.users[demo["id"]] = demo
            _save_users(self.users)

    def create(self, email: str, password: str, display_name: str, home_base: str) -> dict[str, Any]:
        normalized_email = email.strip().lower()
        if len(password) < 8:
            raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")
        if any(user.get("email") == normalized_email for user in self.users.values()):
            raise HTTPException(status_code=409, detail="An account with that email already exists.")
        user = {
            "id": f"user-{uuid4().hex}",
            "email": normalized_email,
            "display_name": display_name.strip() or "VibeTrip traveller",
            "home_base": home_base.strip() or "Singapore",
            "password_hash": _password_hash(password),
        }
        self.users[user["id"]] = user
        _save_users(self.users)
        return user

    def authenticate(self, email: str, password: str) -> dict[str, Any]:
        normalized_email = email.strip().lower()
        user = next((item for item in self.users.values() if item.get("email") == normalized_email), None)
        if not user or not _password_matches(password, user.get("password_hash", "")):
            raise HTTPException(status_code=401, detail="Email or password is incorrect.")
        return user

    def get(self, user_id: str) -> dict[str, Any] | None:
        return self.users.get(user_id)

    def update_profile(self, user_id: str, display_name: str, home_base: str) -> dict[str, Any] | None:
        user = self.users.get(user_id)
        if not user:
            return None
        user["display_name"] = display_name.strip() or user["display_name"]
        user["home_base"] = home_base.strip() or user["home_base"]
        _save_users(self.users)
        return user


auth_repository = LocalAuthRepository()


def issue_session(user: dict[str, Any]) -> str:
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode(json.dumps({"sub": user["id"], "exp": int(time.time()) + SESSION_SECONDS}, separators=(",", ":")).encode())
    message = f"{header}.{payload}".encode("ascii")
    signature = _encode(hmac.new(AUTH_SECRET.encode("utf-8"), message, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def current_user_from_token(token: str) -> dict[str, Any] | None:
    try:
        header, payload, signature = token.split(".", 2)
        message = f"{header}.{payload}".encode("ascii")
        expected = _encode(hmac.new(AUTH_SECRET.encode("utf-8"), message, hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        claims = json.loads(_decode(payload))
        if int(claims.get("exp", 0)) < int(time.time()):
            return None
        return auth_repository.get(str(claims.get("sub")))
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def get_current_user(request: Request) -> dict[str, Any]:
    token = request.cookies.get(SESSION_COOKIE)
    authorization = request.headers.get("Authorization", "")
    if not token and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    user = current_user_from_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return user
