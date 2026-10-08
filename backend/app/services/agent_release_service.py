from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from uuid import uuid4

from app.core.config import settings
from app.core.user_context import SYSTEM_OWNER_ID
from app.schemas.agent_release import (
    AgentRelease,
    AgentReleaseListResponse,
    AgentReleaseSnapshot,
    AgentReleaseState,
)
from app.services.sqlite_state_store import sqlite_state_store


class AgentReleaseService:
    """Stores immutable, evidence-backed Agent release records."""

    _namespace = "agent_releases"
    _max_releases = 30

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._releases = self._load()

    def response(self) -> AgentReleaseListResponse:
        with self._lock:
            active = next(
                (item for item in self._releases if item.state == AgentReleaseState.active),
                None,
            )
            return AgentReleaseListResponse(
                generated_at=datetime.now(timezone.utc),
                active_release_id=active.release_id if active else None,
                releases=list(self._releases),
            )

    def active_reference(self) -> tuple[str | None, str | None, str | None]:
        with self._lock:
            active = next(
                (item for item in self._releases if item.state == AgentReleaseState.active),
                None,
            )
            if active is None:
                return None, None, None
            return active.release_id, active.label, active.state.value

    def create_candidate(
        self,
        *,
        label: str,
        note: str | None,
        snapshot: AgentReleaseSnapshot,
    ) -> AgentRelease:
        now = datetime.now(timezone.utc)
        release = AgentRelease(
            release_id=f"agent-{now.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}",
            label=label.strip(),
            note=note.strip() if note and note.strip() else None,
            state=AgentReleaseState.candidate,
            created_at=now,
            snapshot=snapshot,
        )
        with self._lock:
            self._releases = (release, *self._releases)[: self._max_releases]
            self._persist()
        return release

    def promote(self, release_id: str, *, current_fingerprint: str) -> AgentRelease:
        return self._activate(
            release_id,
            current_fingerprint=current_fingerprint,
            allowed_state=AgentReleaseState.candidate,
            action="promote",
        )

    def rollback(self, release_id: str, *, current_fingerprint: str) -> AgentRelease:
        return self._activate(
            release_id,
            current_fingerprint=current_fingerprint,
            allowed_state=AgentReleaseState.superseded,
            action="rollback",
        )

    def _activate(
        self,
        release_id: str,
        *,
        current_fingerprint: str,
        allowed_state: AgentReleaseState,
        action: str,
    ) -> AgentRelease:
        with self._lock:
            target = next(
                (item for item in self._releases if item.release_id == release_id),
                None,
            )
            if target is None:
                raise ValueError("Agent release not found")
            if target.state != allowed_state:
                raise ValueError(
                    f"Only a {allowed_state.value} Agent release can be used for {action}"
                )
            if target.snapshot.runtime_fingerprint != current_fingerprint:
                raise ValueError(
                    "Current runtime or RAG knowledge differs from this release snapshot"
                )

            now = datetime.now(timezone.utc)
            updated: list[AgentRelease] = []
            activated: AgentRelease | None = None
            for release in self._releases:
                if release.release_id == target.release_id:
                    activated = release.model_copy(
                        update={
                            "state": AgentReleaseState.active,
                            "activated_at": now,
                            "superseded_at": None,
                        }
                    )
                    updated.append(activated)
                elif release.state == AgentReleaseState.active:
                    updated.append(
                        release.model_copy(
                            update={
                                "state": AgentReleaseState.superseded,
                                "superseded_at": now,
                            }
                        )
                    )
                else:
                    updated.append(release)
            self._releases = tuple(updated)
            self._persist()
            if activated is None:
                raise RuntimeError("Agent release activation did not produce a release")
            return activated

    @staticmethod
    def runtime_fingerprint(
        *,
        app_version: str,
        model_provider: str,
        model_strategy: str,
        runtime_model: str | None,
        knowledge_version_id: str | None,
    ) -> str:
        payload = {
            "app_version": app_version,
            "model_provider": model_provider,
            "model_strategy": model_strategy,
            "runtime_model": runtime_model,
            "knowledge_version_id": knowledge_version_id,
        }
        encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _load(self) -> tuple[AgentRelease, ...]:
        payload = sqlite_state_store.load_json(
            self._namespace,
            settings.local_agent_release_path,
            owner_id=SYSTEM_OWNER_ID,
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("releases"), list):
            return ()
        releases: list[AgentRelease] = []
        for item in payload["releases"]:
            try:
                releases.append(AgentRelease.model_validate(item))
            except (TypeError, ValueError):
                continue
        return tuple(sorted(releases, key=lambda item: item.created_at, reverse=True)[: self._max_releases])

    def _persist(self) -> None:
        sqlite_state_store.save_json(
            self._namespace,
            {"releases": [item.model_dump(mode="json") for item in self._releases]},
            owner_id=SYSTEM_OWNER_ID,
        )


agent_release_service = AgentReleaseService()
