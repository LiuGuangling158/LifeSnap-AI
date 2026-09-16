from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from binascii import Error as BinasciiError
from datetime import datetime, timezone
from uuid import uuid4

from app.core.config import settings


class AdminSessionError(ValueError):
    pass


class AdminAuthService:
    def create_session(self) -> tuple[str, datetime, int]:
        if not settings.admin_api_key:
            raise AdminSessionError("Admin API key is not configured")
        ttl_seconds = max(60, settings.admin_session_ttl_minutes * 60)
        issued_at = int(time.time())
        expires_at = issued_at + ttl_seconds
        payload = {
            "sub": "lifesnap-admin",
            "role": "admin",
            "iat": issued_at,
            "exp": expires_at,
            "jti": uuid4().hex,
        }
        body = self._b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        signature = self._signature(body)
        return f"{body}.{signature}", datetime.fromtimestamp(expires_at, tz=timezone.utc), ttl_seconds

    def validate_bearer(self, authorization: str | None) -> bool:
        if not authorization:
            return False
        scheme, _, token = authorization.partition(" ")
        if scheme.casefold() != "bearer" or not token.strip():
            return False
        return self.validate_token(token.strip())

    def validate_token(self, token: str) -> bool:
        if not settings.admin_api_key:
            return False
        body, separator, signature = token.partition(".")
        if separator != "." or not body or not signature:
            return False
        expected_signature = self._signature(body)
        if not hmac.compare_digest(signature, expected_signature):
            return False
        try:
            payload = json.loads(self._b64decode(body).decode("utf-8"))
        except (BinasciiError, ValueError, TypeError, UnicodeDecodeError):
            return False
        if payload.get("role") != "admin" or payload.get("sub") != "lifesnap-admin":
            return False
        try:
            expires_at = int(payload.get("exp"))
        except (TypeError, ValueError):
            return False
        return expires_at > int(time.time())

    def _signature(self, body: str) -> str:
        secret = (settings.admin_api_key or "").encode("utf-8")
        digest = hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest()
        return self._b64encode(digest)

    def _b64encode(self, value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    def _b64decode(self, value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding)


admin_auth_service = AdminAuthService()
