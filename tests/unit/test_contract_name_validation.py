from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from playground.services.contracting import (
    ContractingService,
    _valid_contract_name,
)


class ContractNameValidationTest(unittest.TestCase):
    def test_valid_name_pattern(self) -> None:
        valid = [
            "demo",
            "Contract_1",
            "A" * 64,
            "a1",
        ]
        for name in valid:
            with self.subTest(name=name):
                self.assertTrue(_valid_contract_name(name))

    def test_invalid_name_pattern(self) -> None:
        invalid = [
            "",
            "with-dash",
            "folder/name",
            "..",
            "a" * 65,
        ]
        for name in invalid:
            with self.subTest(name=name):
                self.assertFalse(_valid_contract_name(name))

    def test_deploy_rejects_invalid_names_early(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ContractingService(storage_home=Path(tmpdir))
            with self.assertRaises(ValueError):
                service.deploy("bad/name", "export const name = 1")
            with self.assertRaises(ValueError):
                service.deploy("a" * 65, "export const name = 1")


if __name__ == "__main__":
    unittest.main()
