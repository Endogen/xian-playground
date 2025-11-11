from __future__ import annotations

import unittest

from playground.services.worker import (
    ContractWorkerInvocationError,
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


if __name__ == "__main__":
    unittest.main()
