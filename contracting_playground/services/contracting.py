from __future__ import annotations

import ast
import decimal
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from contracting import constants
from contracting.client import ContractingClient
from contracting.storage import hdf5
from contracting.storage.driver import Driver
from contracting.stdlib.bridge.decimal import ContractingDecimal
from contracting.stdlib.bridge.time import Datetime


def _default_storage_home() -> Path:
    """Return the storage directory used by the in-app client."""
    root = Path(__file__).resolve().parent.parent
    storage = root / ".contract_state"
    storage.mkdir(parents=True, exist_ok=True)
    return storage


def _is_export_decorator(node: ast.AST) -> bool:
    """Return True if the decorator node represents `@export`."""
    if isinstance(node, ast.Name):
        return node.id in {"export", "__export"}
    if isinstance(node, ast.Attribute):
        return node.attr in {"export", "__export"}
    if isinstance(node, ast.Call):
        return _is_export_decorator(node.func)
    return False


def _serialize_value(value: Any) -> Any:
    """Convert contracting values to JSON-serializable primitives."""
    if isinstance(value, ContractingDecimal):
        return str(value)
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, Datetime):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize_value(v) for v in value]
    return value


@dataclass
class ContractingCallResult:
    result: Any

    def as_string(self) -> str:
        if self.result is None:
            return "Success (no return value)"
        serialized = _serialize_value(self.result)
        if isinstance(serialized, (dict, list)):
            return json.dumps(serialized, indent=2, sort_keys=True)
        return str(serialized)


class ContractingService:
    """Facade around `ContractingClient` with basic locking and helpers."""

    def __init__(self, storage_home: Path | None = None):
        storage_home = storage_home or _default_storage_home()
        self._lock = threading.RLock()
        self._driver = Driver(storage_home=storage_home)
        self._client = ContractingClient(driver=self._driver)

    def get_signer(self) -> str:
        with self._lock:
            return self._client.signer

    def set_signer(self, signer: str) -> str:
        clean = (signer or "").strip()
        if not clean:
            raise ValueError("Signer cannot be empty.")

        with self._lock:
            self._client.signer = clean

        return clean

    def deploy(self, name: str, code: str) -> None:
        """Deploy a contract by name."""
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("Contract name cannot be empty.")
        if clean_name == "submission":
            raise ValueError("Contract name 'submission' is reserved.")
        if not code or not code.strip():
            raise ValueError("Contract code cannot be empty.")

        with self._lock:
            self._client.submit(code, name=clean_name)
            self._driver.commit()

    def list_contracts(self) -> List[str]:
        with self._lock:
            contract_files = self._driver.get_contract_files()
        return sorted(name for name in contract_files if name != "submission")

    def list_functions(self, contract: str) -> List[str]:
        if not contract:
            return []

        with self._lock:
            source = self._driver.get_contract(contract)

        if not source:
            return []

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        exports: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if any(_is_export_decorator(dec) for dec in node.decorator_list):
                    exports.append(node.name)

        return sorted(exports)

    def call(self, contract: str, function: str, kwargs: Dict[str, Any]) -> ContractingCallResult:
        if not contract:
            raise ValueError("No contract selected.")
        if not function:
            raise ValueError("No function selected.")

        with self._lock:
            abstract = self._client.get_contract(contract)
            if abstract is None:
                raise ValueError(f"Contract '{contract}' is not deployed.")
            if not hasattr(abstract, function):
                raise ValueError(f"Function '{function}' not found on contract '{contract}'.")

            fn = getattr(abstract, function)
            result = fn(**kwargs)
            self._driver.commit()

        return ContractingCallResult(result=result)

    def dump_state(self, show_internal: bool = False) -> str:
        snapshot: Dict[str, Dict[str, Any]] = {}

        with self._lock:
            contract_files = self._driver.get_contract_files()
            for name in contract_files:
                file_path = self._driver.contract_state / name
                keys = hdf5.get_all_keys_from_file(str(file_path))
                snapshot[name] = {
                    key: _serialize_value(value)
                    for key in keys
                    if (show_internal or not key.startswith("__"))
                    if (value := hdf5.get_value_from_disk(
                        str(file_path),
                        key.replace(constants.DELIMITER, constants.HDF5_GROUP_SEPARATOR),
                    )) is not None
                }

            runtime_snapshot: Dict[str, Dict[str, Any]] = {}
            for path in sorted(self._driver.run_state.iterdir()):
                if not path.is_file():
                    continue
                keys = hdf5.get_all_keys_from_file(str(path))
                runtime_snapshot[path.name] = {
                    key: _serialize_value(value)
                    for key in keys
                    if (show_internal or not key.startswith("__"))
                    if (value := hdf5.get_value_from_disk(
                        str(path),
                        key.replace(constants.DELIMITER, constants.HDF5_GROUP_SEPARATOR),
                    )) is not None
                }

            if runtime_snapshot:
                snapshot["__runtime__"] = runtime_snapshot

        return json.dumps(snapshot, indent=2, sort_keys=True)


contracting_service = ContractingService()
