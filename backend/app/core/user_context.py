from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
from threading import RLock


LEGACY_OWNER_ID = "legacy"
SYSTEM_OWNER_ID = "system"

_owner_id: ContextVar[str] = ContextVar("lifesnap_owner_id", default=LEGACY_OWNER_ID)
user_state_lock = asyncio.Lock()
user_registration_lock = RLock()


def current_owner_id() -> str:
    return _owner_id.get()


def set_current_owner_id(owner_id: str) -> Token[str]:
    return _owner_id.set(owner_id)


def reset_current_owner_id(token: Token[str]) -> None:
    _owner_id.reset(token)
