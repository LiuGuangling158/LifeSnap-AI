from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, Header, HTTPException, status

from app.core.config import settings
from app.core.user_context import (
    reset_current_owner_id,
    set_current_owner_id,
    user_registration_lock,
    user_state_lock,
)
from app.schemas.auth import AuthLoginRequest, AuthRegisterRequest, AuthSessionResponse, AuthUser
from app.services.sqlite_state_store import sqlite_state_store


class AuthService:
    _username_pattern = re.compile(r"^[A-Za-z0-9_.-]{3,40}$")

    def register(self, payload: AuthRegisterRequest) -> AuthSessionResponse:
        username = payload.username.strip().casefold()
        if not self._username_pattern.fullmatch(username):
            raise ValueError("Username may contain letters, numbers, dots, underscores, and hyphens only")
        now = datetime.now(timezone.utc)
        user_id = uuid4().hex
        display_name = (payload.display_name or username).strip()[:80] or username
        with user_registration_lock:
            connection = self._connect()
            try:
                first_user = int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]) == 0
                role = "admin" if first_user else "user"
                connection.execute(
                    """
                    INSERT INTO users(user_id, username, password_hash, role, display_name, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        username,
                        self._hash_password(payload.password),
                        role,
                        display_name,
                        now.isoformat(),
                        now.isoformat(),
                    ),
                )
                connection.commit()
                if first_user:
                    sqlite_state_store.claim_legacy_owner(user_id)
            except sqlite3.IntegrityError as exc:
                raise ValueError("Username is already in use") from exc
            finally:
                connection.close()
        return self._session_for(self.get_user(user_id))

    def login(self, payload: AuthLoginRequest) -> AuthSessionResponse:
        user = self._find_by_username(payload.username)
        if user is None or not self._verify_password(payload.password, user["password_hash"]):
            raise ValueError("Invalid username or password")
        return self._session_for(self._to_user(user))

    def current_user(self, authorization: str | None) -> AuthUser | None:
        token = self._bearer_token(authorization)
        if token is None:
            return None
        payload = self._verify_token(token)
        if payload is None:
            return None
        user = self.get_user(str(payload.get("sub") or ""))
        if user is None or user.role != payload.get("role"):
            return None
        return user

    def get_user(self, user_id: str) -> AuthUser | None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT user_id, username, display_name, role, created_at FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        finally:
            connection.close()
        return self._to_user(row) if row is not None else None

    def _session_for(self, user: AuthUser | None) -> AuthSessionResponse:
        if user is None:
            raise ValueError("User account was not found")
        ttl_seconds = max(300, settings.auth_session_ttl_minutes * 60)
        issued_at = int(time.time())
        expires_at = issued_at + ttl_seconds
        payload = {"sub": user.user_id, "role": user.role, "iat": issued_at, "exp": expires_at, "jti": uuid4().hex}
        body = self._b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        token = f"{body}.{self._signature(body)}"
        return AuthSessionResponse(
            access_token=token,
            expires_at=datetime.fromtimestamp(expires_at, tz=timezone.utc),
            expires_in_seconds=ttl_seconds,
            user=user,
        )

    def _find_by_username(self, username: str) -> sqlite3.Row | None:
        connection = self._connect()
        try:
            return connection.execute(
                "SELECT user_id, username, password_hash, role, display_name, created_at FROM users WHERE username = ?",
                (username.strip().casefold(),),
            ).fetchone()
        finally:
            connection.close()

    def _to_user(self, row: sqlite3.Row | None) -> AuthUser | None:
        if row is None:
            return None
        return AuthUser(
            user_id=str(row["user_id"]),
            username=str(row["username"]),
            display_name=str(row["display_name"]),
            role=str(row["role"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(settings.local_database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _hash_password(self, password: str) -> str:
        salt = os.urandom(16)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
        return "$".join(("scrypt", "16384", "8", "1", self._b64encode(salt), self._b64encode(digest)))

    def _verify_password(self, password: str, encoded: str) -> bool:
        try:
            algorithm, n, r, p, salt, digest = encoded.split("$")
            if algorithm != "scrypt":
                return False
            candidate = hashlib.scrypt(
                password.encode("utf-8"),
                salt=self._b64decode(salt),
                n=int(n),
                r=int(r),
                p=int(p),
            )
            return hmac.compare_digest(candidate, self._b64decode(digest))
        except (TypeError, ValueError):
            return False

    def _bearer_token(self, authorization: str | None) -> str | None:
        scheme, _, token = (authorization or "").partition(" ")
        return token.strip() if scheme.casefold() == "bearer" and token.strip() else None

    def _verify_token(self, token: str) -> dict[str, object] | None:
        body, separator, signature = token.partition(".")
        if separator != "." or not hmac.compare_digest(signature, self._signature(body)):
            return None
        try:
            payload = json.loads(self._b64decode(body).decode("utf-8"))
            if int(payload.get("exp") or 0) <= int(time.time()):
                return None
            if not isinstance(payload.get("sub"), str) or payload.get("role") not in {"user", "admin"}:
                return None
            return payload
        except (TypeError, ValueError, UnicodeDecodeError):
            return None

    def _signature(self, body: str) -> str:
        secret = (settings.auth_session_secret or settings.admin_api_key or "").encode("utf-8")
        return self._b64encode(hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest())

    def _b64encode(self, value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    def _b64decode(self, value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


auth_service = AuthService()


async def require_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    user = auth_service.current_user(authorization)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    token = set_current_owner_id(user.user_id)
    await user_state_lock.acquire()
    try:
        _reload_user_scoped_state()
        yield user
    finally:
        user_state_lock.release()
        reset_current_owner_id(token)


def require_admin_user(user: AuthUser = Depends(require_current_user)) -> AuthUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required")
    return user


def _reload_user_scoped_state() -> None:
    from app.services.attachment_store import attachment_store
    from app.services.audit_log_store import audit_log_store
    from app.services.bill_candidate_store import bill_candidate_store
    from app.services.bill_store import bill_store
    from app.services.diary_candidate_store import diary_candidate_store
    from app.services.diary_store import diary_store
    from app.services.idempotency_store import idempotency_store
    from app.services.settings_store import settings_store
    from app.services.task_candidate_store import task_candidate_store
    from app.services.task_store import task_store

    for store in (
        bill_store,
        task_store,
        diary_store,
        attachment_store,
        bill_candidate_store,
        task_candidate_store,
        diary_candidate_store,
        settings_store,
        idempotency_store,
        audit_log_store,
    ):
        store.reload_for_current_owner()
