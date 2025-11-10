"""Filesystem-backed session repository and metadata helpers."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .contracting import DEFAULT_ENVIRONMENT
from ..defaults import DEFAULT_CONTRACT, DEFAULT_CONTRACT_NAME, DEFAULT_KWARGS_INPUT


SESSION_FILE_NAME = "session.json"
SESSION_UI_FIELDS: tuple[str, ...] = (
    "code_editor",
    "contract_name",
    "kwargs_input",
    "load_view_decompiled",
    "expanded_panel",
    "selected_contract",
    "load_selected_contract",
    "function_name",
    "show_internal_state",
)

DEFAULT_UI_STATE: Dict[str, Any] = {
    "code_editor": DEFAULT_CONTRACT,
    "contract_name": DEFAULT_CONTRACT_NAME,
    "kwargs_input": DEFAULT_KWARGS_INPUT,
    "load_view_decompiled": True,
    "expanded_panel": "",
    "selected_contract": "",
    "load_selected_contract": "",
    "function_name": "",
    "show_internal_state": False,
}


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class SessionNotFoundError(FileNotFoundError):
    """Raised when a session directory/metadata cannot be found."""


@dataclass(slots=True)
class SessionMetadata:
    session_id: str
    created_at: str
    updated_at: str
    environment: Dict[str, Any] = field(default_factory=dict)
    ui_state: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(cls, session_id: str) -> "SessionMetadata":
        now = _utcnow()
        return cls(
            session_id=session_id,
            created_at=now,
            updated_at=now,
            environment=dict(DEFAULT_ENVIRONMENT),
            ui_state=dict(DEFAULT_UI_STATE),
        )


class SessionRepository:
    """Manage session directories and metadata stored on disk."""

    def __init__(self, root: Path | None = None):
        base = root or Path(__file__).resolve().parent.parent / ".sessions"
        self._root = base
        self._root.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, threading.RLock] = {}
        self._locks_lock = threading.RLock()

    @property
    def root(self) -> Path:
        return self._root

    @staticmethod
    def _normalize_session_id(session_id: str | None) -> str | None:
        if not session_id:
            return None
        session_id = session_id.strip().lower()
        if not session_id:
            return None
        return session_id

    @staticmethod
    def is_valid_session_id(session_id: str | None) -> bool:
        session_id = SessionRepository._normalize_session_id(session_id)
        if session_id is None:
            return False
        if len(session_id) != 32:
            return False
        try:
            uuid.UUID(hex=session_id, version=4)
        except ValueError:
            return False
        return True

    def _lock_for(self, session_id: str) -> threading.RLock:
        with self._locks_lock:
            if session_id not in self._locks:
                self._locks[session_id] = threading.RLock()
            return self._locks[session_id]

    def _session_dir(self, session_id: str) -> Path:
        return self._root / session_id

    def storage_home(self, session_id: str) -> Path:
        """Return the storage directory passed to ContractingService."""
        path = self._session_dir(session_id)
        (path / "contract_state").mkdir(parents=True, exist_ok=True)
        (path / "run_state").mkdir(parents=True, exist_ok=True)
        return path

    def _metadata_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / SESSION_FILE_NAME

    def session_exists(self, session_id: str) -> bool:
        session_id = self._normalize_session_id(session_id)
        if session_id is None:
            return False
        return self._metadata_path(session_id).exists()

    def create_session(self) -> SessionMetadata:
        """Create a new session with a unique identifier."""
        while True:
            session_id = uuid.uuid4().hex
            path = self._session_dir(session_id)
            if path.exists():
                continue
            path.mkdir(parents=True, exist_ok=True)
            metadata = SessionMetadata.new(session_id)
            self._write_metadata(metadata)
            self.storage_home(session_id)
            return metadata

    def load_metadata(self, session_id: str) -> SessionMetadata:
        """Load metadata for an existing session."""
        normalized = self._normalize_session_id(session_id)
        if normalized is None:
            raise SessionNotFoundError(session_id)
        path = self._metadata_path(normalized)
        if not path.exists():
            raise SessionNotFoundError(session_id)
        lock = self._lock_for(normalized)
        with lock:
            data = json.loads(path.read_text())
        metadata = SessionMetadata(
            session_id=data["session_id"],
            created_at=data["created_at"],
            updated_at=data.get("updated_at", data["created_at"]),
            environment=data.get("environment", dict(DEFAULT_ENVIRONMENT)),
            ui_state=data.get("ui_state", dict(DEFAULT_UI_STATE)),
        )
        # Ensure storage directories exist even if metadata survived but folders were deleted.
        self.storage_home(metadata.session_id)
        return metadata

    def update_metadata(
        self,
        session_id: str,
        *,
        environment: Dict[str, Any] | None = None,
        ui_state: Dict[str, Any] | None = None,
    ) -> SessionMetadata:
        """Update stored metadata fields."""
        metadata = self.load_metadata(session_id)
        updates = {}
        if environment is not None:
            updates["environment"] = environment
        if ui_state is not None:
            filtered_state = {
                key: ui_state.get(key, DEFAULT_UI_STATE.get(key))
                for key in SESSION_UI_FIELDS
            }
            updates["ui_state"] = filtered_state
        if updates:
            metadata = replace(metadata, **updates, updated_at=_utcnow())
            self._write_metadata(metadata)
        else:
            self.touch_session(session_id)
        return metadata

    def touch_session(self, session_id: str) -> None:
        """Bump the updated_at timestamp without mutating stored fields."""
        metadata = self.load_metadata(session_id)
        metadata.updated_at = _utcnow()
        self._write_metadata(metadata)

    def _write_metadata(self, metadata: SessionMetadata) -> None:
        path = self._metadata_path(metadata.session_id)
        lock = self._lock_for(metadata.session_id)
        payload = {
            "session_id": metadata.session_id,
            "created_at": metadata.created_at,
            "updated_at": metadata.updated_at,
            "environment": metadata.environment,
            "ui_state": metadata.ui_state,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        with lock:
            tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
            tmp_path.replace(path)
