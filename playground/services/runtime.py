"""Session-scoped access to contracting services and metadata."""

from __future__ import annotations

import threading
from typing import Any, Dict

from .contracting import ContractDetails, ContractExportInfo
from .worker import ContractingWorker, SessionServiceProxy
from .sessions import SessionMetadata, SessionNotFoundError, SessionRepository


SESSION_COOKIE_NAME = "xian_session_id"
SESSION_COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days


class SessionRuntimeManager:
    """Coordinate per-session ContractingService instances + metadata."""

    def __init__(self, repository: SessionRepository | None = None):
        self._repository = repository or SessionRepository()
        self._services: dict[str, SessionServiceProxy] = {}
        self._workers: dict[str, ContractingWorker] = {}
        self._services_lock = threading.RLock()

    @property
    def repository(self) -> SessionRepository:
        return self._repository

    def resolve_or_create(self, session_id: str | None) -> tuple[SessionMetadata, bool]:
        """Return existing metadata for session_id or create a new session."""
        if session_id and SessionRepository.is_valid_session_id(session_id):
            try:
                metadata = self._repository.load_metadata(session_id)
                return metadata, False
            except SessionNotFoundError:
                pass
        metadata = self._repository.create_session()
        return metadata, True

    def create_session(self) -> SessionMetadata:
        return self._repository.create_session()

    def ensure_exists(self, session_id: str) -> SessionMetadata:
        return self._repository.load_metadata(session_id)

    def session_exists(self, session_id: str) -> bool:
        return self._repository.session_exists(session_id)

    def get_ui_state(self, session_id: str) -> Dict[str, Any]:
        metadata = self.ensure_exists(session_id)
        return dict(metadata.ui_state)

    def save_ui_state(self, session_id: str, ui_state: Dict[str, Any]) -> None:
        self._repository.update_metadata(session_id, ui_state=ui_state)

    def get_environment_snapshot(self, session_id: str) -> Dict[str, Any]:
        service = self._get_service(session_id)
        return service.snapshot_environment()

    def update_environment_snapshot(self, session_id: str) -> None:
        service = self._get_service(session_id)
        snapshot = service.snapshot_environment()
        self._repository.update_metadata(session_id, environment=snapshot)

    def list_contracts(self, session_id: str) -> list[str]:
        service = self._get_service(session_id)
        return service.list_contracts()

    def get_export_metadata(self, session_id: str, contract: str) -> list[ContractExportInfo]:
        service = self._get_service(session_id)
        return service.get_export_metadata(contract)

    def get_contract_details(self, session_id: str, contract: str) -> ContractDetails:
        service = self._get_service(session_id)
        return service.get_contract_details(contract)

    def deploy(self, session_id: str, name: str, code: str) -> None:
        service = self._get_service(session_id)
        service.deploy(name, code)

    def call(self, session_id: str, contract: str, function: str, kwargs: Dict[str, Any]):
        service = self._get_service(session_id)
        return service.call(contract, function, kwargs)

    def dump_state(self, session_id: str, show_internal: bool) -> str:
        service = self._get_service(session_id)
        return service.dump_state(show_internal)

    def apply_state_snapshot(self, session_id: str, snapshot: Dict[str, Any]) -> None:
        service = self._get_service(session_id)
        service.apply_state_snapshot(snapshot)

    def remove_contract(self, session_id: str, name: str) -> None:
        service = self._get_service(session_id)
        service.remove_contract(name)

    def reset_state(self, session_id: str) -> SessionMetadata:
        service = self._get_service(session_id)
        service.reset_state()
        metadata = SessionMetadata.new(session_id)
        metadata.environment = service.snapshot_environment()
        metadata.updated_at = metadata.created_at
        self._repository.update_metadata(
            session_id,
            environment=metadata.environment,
            ui_state=metadata.ui_state,
        )
        return metadata

    def set_environment_var(self, session_id: str, key: str, value: Any) -> Any:
        service = self._get_service(session_id)
        result = service.set_environment_var(key, value)
        self.update_environment_snapshot(session_id)
        return result

    def remove_environment_var(self, session_id: str, key: str) -> None:
        service = self._get_service(session_id)
        service.remove_environment_var(key)
        self.update_environment_snapshot(session_id)

    def set_signer(self, session_id: str, signer: str) -> str:
        service = self._get_service(session_id)
        updated = service.set_signer(signer)
        self.update_environment_snapshot(session_id)
        return updated

    def get_environment(self, session_id: str) -> Dict[str, Any]:
        service = self._get_service(session_id)
        return service.get_environment()

    def _reinitialize_service(self, session_id: str) -> ContractingService:
        """Dispose and recreate the ContractingService for a session."""
        with self._services_lock:
            self._services.pop(session_id, None)
        return self._get_service(session_id)

    def _get_service(self, session_id: str) -> SessionServiceProxy:
        session_id = SessionRepository._normalize_session_id(session_id)
        if not session_id:
            raise SessionNotFoundError("missing-session-id")
        with self._services_lock:
            cached = self._services.get(session_id)
            if cached:
                worker = self._workers.get(session_id)
                if worker and worker._dead:
                    return self._restart_service(session_id)
                return cached

            metadata = self._repository.load_metadata(session_id)
            storage_home = self._repository.storage_home(session_id)
            worker = ContractingWorker(storage_home=storage_home)
            worker.start()
            proxy = SessionServiceProxy(worker)
            proxy.hydrate_environment(metadata.environment)
            self._services[session_id] = proxy
            self._workers[session_id] = worker
            return proxy

    def _restart_service(self, session_id: str) -> SessionServiceProxy:
        old_worker = self._workers.pop(session_id, None)
        if old_worker:
            old_worker.stop()
        old_proxy = self._services.pop(session_id, None)
        if old_proxy:
            try:
                old_proxy.stop()
            except Exception:
                pass
        metadata = self._repository.load_metadata(session_id)
        storage_home = self._repository.storage_home(session_id)
        worker = ContractingWorker(storage_home=storage_home)
        worker.start()
        proxy = SessionServiceProxy(worker)
        proxy.hydrate_environment(metadata.environment)
        self._services[session_id] = proxy
        self._workers[session_id] = worker
        return proxy

    def shutdown(self):
        with self._services_lock:
            for proxy in self._services.values():
                proxy.stop()
            self._services.clear()
            self._workers.clear()

    def close_session(self, session_id: str) -> None:
        normalized = SessionRepository._normalize_session_id(session_id)
        if not normalized:
            return
        with self._services_lock:
            worker = self._workers.pop(normalized, None)
            if worker:
                worker.stop()
            proxy = self._services.pop(normalized, None)
            if proxy:
                try:
                    proxy.stop()
                except Exception:
                    pass


session_runtime = SessionRuntimeManager()

import atexit

atexit.register(session_runtime.shutdown)
