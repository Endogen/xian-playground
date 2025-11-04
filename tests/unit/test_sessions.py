from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from playground.services.sessions import SessionNotFoundError, SessionRepository


class SessionRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = SessionRepository(root=Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_and_load_session(self):
        metadata = self.repo.create_session()
        self.assertTrue(self.repo.session_exists(metadata.session_id))
        loaded = self.repo.load_metadata(metadata.session_id)
        self.assertEqual(metadata.session_id, loaded.session_id)
        storage = self.repo.storage_home(metadata.session_id)
        self.assertTrue(storage.joinpath("contract_state").exists())
        self.assertTrue(storage.joinpath("run_state").exists())

    def test_update_metadata_fields(self):
        meta = self.repo.create_session()
        self.repo.update_metadata(
            meta.session_id,
            ui_state={"contract_name": "con_test", "code_editor": "pass"},
            environment={"signer": "tester"},
        )
        loaded = self.repo.load_metadata(meta.session_id)
        self.assertEqual("con_test", loaded.ui_state["contract_name"])
        self.assertEqual("pass", loaded.ui_state["code_editor"])
        self.assertEqual("tester", loaded.environment["signer"])

    def test_load_missing_session(self):
        with self.assertRaises(SessionNotFoundError):
            self.repo.load_metadata("deadbeefdeadbeefdeadbeefdeadbeef")


if __name__ == "__main__":
    unittest.main()
