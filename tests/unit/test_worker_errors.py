from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from playground.services.worker import (
    ContractWorkerInvocationError,
    ContractWorkerTimeoutError,
    ContractingWorker,
    RemoteExceptionPayload,
    _serialize_exception,
)


class WorkerErrorUtilitiesTest(unittest.TestCase):
    def test_serialize_exception_includes_traceback(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError as exc:  # noqa: PERF203 - deliberate test path
            payload = _serialize_exception(exc)

        self.assertEqual(payload["exc_type"], "ValueError")
        self.assertTrue(payload["traceback"].startswith("Traceback"))
        self.assertIn("ValueError: boom", payload["traceback"])

    def test_remote_payload_round_trip(self) -> None:
        payload = RemoteExceptionPayload.from_raw(
            {
                "exc_type": "ValueError",
                "exc_module": "builtins",
                "message": "boom",
                "traceback": "trace",
            }
        )
        err = ContractWorkerInvocationError(command="call", payload=payload)

        self.assertEqual(err.remote_type, "ValueError")
        self.assertEqual(err.remote_message, "boom")
        self.assertIn("call failed", str(err))
        self.assertEqual(err.pretty_remote_traceback(), "trace")

    def test_timeout_marks_worker_dead_and_closes_resources(self) -> None:
        class FakeConn:
            def __init__(self, *, poll_result: bool = False):
                self.poll_result = poll_result
                self.closed = False

            def send(self, _):
                return None

            def poll(self, timeout=None):
                self.last_timeout = timeout
                return self.poll_result

            def recv(self):
                raise AssertionError("recv should not be called on timeout")

            def close(self):
                self.closed = True

        worker = ContractingWorker(storage_home=Path(tempfile.gettempdir()))
        worker._lock = threading.Lock()
        parent_conn = FakeConn(poll_result=False)
        child_conn = FakeConn(poll_result=False)
        worker._parent_conn = parent_conn
        worker._child_conn = child_conn

        terminated = {"value": False}
        joined = {"value": None}
        worker.is_alive = lambda: True  # type: ignore[method-assign]
        worker.terminate = lambda: terminated.__setitem__("value", True)  # type: ignore[method-assign]
        worker.join = lambda timeout=None: joined.__setitem__("value", timeout)  # type: ignore[method-assign]

        with self.assertRaises(ContractWorkerTimeoutError):
            worker.invoke("noop")

        self.assertTrue(worker._dead)
        self.assertTrue(worker._stopped)
        self.assertIsNone(worker._parent_conn)
        self.assertIsNone(worker._child_conn)
        self.assertTrue(parent_conn.closed)
        self.assertTrue(child_conn.closed)
        self.assertTrue(terminated["value"])
        self.assertEqual(joined["value"], 1)


if __name__ == "__main__":
    unittest.main()
