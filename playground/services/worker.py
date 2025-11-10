from __future__ import annotations

import atexit
import multiprocessing as mp
import threading
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any, Callable


class ContractingWorker(mp.Process):
    """Run a ContractingService inside an isolated process."""

    def __init__(self, storage_home: Path):
        super().__init__(daemon=True)
        self._storage_home = str(storage_home)
        self._parent_conn: Connection | None = None
        self._child_conn: Connection | None = None
        self._lock = None
        self._stopped = False
        self._dead = False

    def run(self) -> None:
        from .contracting import ContractingService  # Local import for spawn safety

        service = ContractingService(storage_home=Path(self._storage_home))
        conn = self._child_conn
        while True:
            try:
                message = conn.recv()
            except EOFError:
                break
            if not isinstance(message, tuple) or len(message) != 3:
                conn.send(("error", ("ContractingWorker", "invalid message")))
                continue
            command, args, kwargs = message
            if command == "__shutdown__":
                conn.send(("ok", None))
                break
            try:
                target: Callable = getattr(service, command)
            except AttributeError:
                conn.send(("error", ("AttributeError", f"Unknown command {command!r}")))
                continue
            try:
                result = target(*args, **kwargs)
                conn.send(("ok", result))
            except Exception as exc:  # noqa: BLE001
                conn.send(("error", (exc.__class__.__name__, str(exc))))

        conn.close()

    def start(self) -> None:
        parent_conn, child_conn = mp.Pipe()
        self._parent_conn = parent_conn
        self._child_conn = child_conn
        super().start()
        self._lock = threading.Lock()
        self._lock = threading.Lock()

    def invoke(self, command: str, *args, **kwargs):
        if self._stopped:
            raise RuntimeError("Contracting worker has been stopped.")

        lock = self._lock
        if lock is None:
            raise RuntimeError("Worker lock not initialized.")
        with lock:
            conn = self._parent_conn
            if conn is None:
                raise RuntimeError("Worker connection not initialized.")
            try:
                conn.send((command, args, kwargs))
                status, payload = conn.recv()
            except (EOFError, BrokenPipeError):
                self._dead = True
                raise RuntimeError("Contracting worker became unavailable.") from None
        if status == "ok":
            return payload
        exc_type, message = payload
        raise RuntimeError(f"{command} failed: {exc_type}: {message}")

    def stop(self) -> None:
        if self._stopped:
            return
        try:
            lock = self._lock
            if lock is None:
                raise RuntimeError("Worker lock not initialized.")
            with lock:
                conn = self._parent_conn
                if conn is not None:
                    conn.send(("__shutdown__", (), {}))
                    conn.recv()
        except (EOFError, BrokenPipeError):
            pass
        finally:
            if self._parent_conn is not None:
                self._parent_conn.close()
            if self._child_conn is not None:
                self._child_conn.close()
            self.join(timeout=2)
            if self.is_alive():
                self.terminate()
            self._stopped = True
            self._dead = True

    def __getstate__(self):
        state = self.__dict__.copy()
        state['_lock'] = None
        state['_parent_conn'] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._lock = None


class SessionServiceProxy:
    """Thin proxy forwarding attribute access to the worker process."""

    def __init__(
        self,
        worker: ContractingWorker,
        *,
        before_invoke: Callable[[], None] | None = None,
        after_invoke: Callable[[], None] | None = None,
    ):
        self._worker = worker
        self._before_invoke = before_invoke
        self._after_invoke = after_invoke

    def __getattr__(self, item: str):
        def method(*args, **kwargs):
            invoked = False
            if self._before_invoke:
                self._before_invoke()
                invoked = True
            try:
                return self._worker.invoke(item, *args, **kwargs)
            finally:
                if invoked and self._after_invoke:
                    self._after_invoke()

        return method

    def stop(self) -> None:
        self._worker.stop()
