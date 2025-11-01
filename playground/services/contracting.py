from __future__ import annotations

import ast
import decimal
import json
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from contracting import constants
from contracting.client import ContractingClient
from contracting.storage import hdf5
from contracting.storage.driver import Driver
from contracting.stdlib.bridge.decimal import ContractingDecimal
from contracting.stdlib.bridge.time import Datetime


DEFAULT_SIGNER = "demo"
DEFAULT_ENVIRONMENT: Dict[str, str] = {
    "signer": DEFAULT_SIGNER,
    "now": "2024-02-01T12:30:00",
    "block_num": "100",
    "block_hash": "0xabc...",
}

ENVIRONMENT_FIELDS: List[Dict[str, str]] = [
    {
        "key": "signer",
        "label": "signer",
        "tooltip": (
            "Override ctx.signer for executions. Typically this is the Xian wallet "
            "address submitting the transaction; leave blank to keep the default signer."
        ),
        "placeholder": DEFAULT_SIGNER,
    },
    {
        "key": "now",
        "label": "now",
        "tooltip": "Override the execution timestamp returned by ctx.now. Use ISO 8601 input such as 2024-02-01T12:30:00.",
        "placeholder": DEFAULT_ENVIRONMENT["now"],
    },
    {
        "key": "block_num",
        "label": "block_num",
        "tooltip": "Synthetic block height applied when seeding deterministic randomness.",
        "placeholder": DEFAULT_ENVIRONMENT["block_num"],
    },
    {
        "key": "block_hash",
        "label": "block_hash",
        "tooltip": "Block hash string mixed into the randomness seed.",
        "placeholder": DEFAULT_ENVIRONMENT["block_hash"],
    },
]

_ENVIRONMENT_LOOKUP = {field["key"]: field for field in ENVIRONMENT_FIELDS}


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


@dataclass
class ContractExportInfo:
    name: str
    docstring: str = ""


@dataclass
class ContractDetails:
    name: str
    source: str
    exports: List[ContractExportInfo]


class ContractingService:
    """Facade around `ContractingClient` with basic locking and helpers."""

    def __init__(self, storage_home: Path | None = None):
        storage_home = storage_home or _default_storage_home()
        self._lock = threading.RLock()
        self._driver = Driver(storage_home=storage_home)
        self._client = ContractingService._create_client(driver=self._driver)
        self._environment = self._client.environment
        self._apply_default_environment()
        self._prune_environment()

    @staticmethod
    def _create_client(driver: Driver) -> ContractingClient:
        return ContractingClient(driver=driver, signer=DEFAULT_SIGNER)

    def get_signer(self) -> str:
        with self._lock:
            return self._client.signer

    def set_signer(self, signer: str) -> str:
        clean = (signer or "").strip()
        if not clean:
            raise ValueError("Signer cannot be empty.")

        with self._lock:
            self._client.signer = clean

        # Keep the environment mirror in sync so UI displays the current signer.
        self._environment['signer'] = clean

        return clean

    def get_environment(self) -> Dict[str, Any]:
        with self._lock:
            self._prune_environment()
            env = {
                key: self._environment.get(key)
                for key in _ENVIRONMENT_LOOKUP
            }
            env['signer'] = self._client.signer
            return env

    def set_environment_var(self, key: str, value: str) -> Any:
        clean_key = (key or "").strip()
        if not clean_key:
            raise ValueError("Environment key cannot be empty.")
        if clean_key not in _ENVIRONMENT_LOOKUP:
            raise ValueError(f"Environment key '{clean_key}' is not configurable.")

        if clean_key == 'signer':
            clean_value = str(value).strip()
            if clean_value == "":
                clean_value = DEFAULT_SIGNER

            with self._lock:
                self._client.signer = clean_value
                self._environment['signer'] = clean_value
            return clean_value

        if value is None or str(value).strip() == "":
            default = DEFAULT_ENVIRONMENT.get(clean_key, "")
            coerced_default = self._coerce_environment_value(clean_key, default)
            with self._lock:
                self._environment[clean_key] = coerced_default
            return coerced_default

        coerced = self._coerce_environment_value(clean_key, value)

        with self._lock:
            self._environment[clean_key] = coerced

        return coerced

    def remove_environment_var(self, key: str) -> None:
        clean_key = (key or "").strip()
        if not clean_key:
            return
        if clean_key not in _ENVIRONMENT_LOOKUP:
            return
        with self._lock:
            if clean_key == 'signer':
                self._client.signer = DEFAULT_SIGNER
                self._environment['signer'] = DEFAULT_SIGNER
            else:
                default = DEFAULT_ENVIRONMENT.get(clean_key)
                if default is not None:
                    self._environment[clean_key] = self._coerce_environment_value(clean_key, default)
                else:
                    self._environment.pop(clean_key, None)

    def _prune_environment(self) -> None:
        for key in list(self._environment.keys()):
            if key not in _ENVIRONMENT_LOOKUP:
                self._environment.pop(key, None)

    def _apply_default_environment(self) -> None:
        for key, default in DEFAULT_ENVIRONMENT.items():
            if key == "signer":
                self._client.signer = default
                self._environment['signer'] = default
            else:
                current = self._environment.get(key)
                if current in (None, ""):
                    self._environment[key] = self._coerce_environment_value(key, default)

    def _coerce_environment_value(self, key: str, raw: Any) -> Any:
        if key not in _ENVIRONMENT_LOOKUP:
            raise ValueError(f"Environment key '{key}' is not configurable.")

        if isinstance(raw, Datetime):
            return raw

        if key == 'signer':
            return str(raw).strip()

        if key == "now":
            if raw is None or str(raw).strip() == "":
                raise ValueError("Environment['now'] requires an ISO datetime string.")

            text = str(raw).strip()
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError as exc:
                raise ValueError("Invalid ISO format for 'now'.") from exc
            return Datetime._from_datetime(parsed)

        if key == "block_num":
            text = str(raw).strip() or "0"
            try:
                return int(text, 0)
            except ValueError as exc:
                raise ValueError("block_num must be an integer.") from exc

        if key == 'block_hash':
            return str(raw).strip()

        text = str(raw).strip()
        if text == "":
            return ""

        try:
            parsed = json.loads(text)
            return parsed
        except json.JSONDecodeError:
            return text

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

    def apply_state_snapshot(self, snapshot: Dict[str, Any]) -> None:
        if not isinstance(snapshot, dict):
            raise ValueError("State snapshot must be a JSON object.")

        with self._lock:
            for contract, entries in snapshot.items():
                if contract == "__runtime__":
                    continue
                if not isinstance(entries, dict):
                    raise ValueError(f"State for '{contract}' must be an object mapping keys to values.")

                for key, value in entries.items():
                    if not isinstance(key, str):
                        raise ValueError(f"State keys for '{contract}' must be strings.")

                    full_key = contract if key == "" else f"{contract}.{key}"

                    if value is None:
                        self._driver.delete(full_key)
                    else:
                        self._driver.set(full_key, value)

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

        exports = self._parse_exports(source)
        return sorted(export.name for export in exports)

    def get_contract_details(self, contract: str) -> ContractDetails:
        clean_name = (contract or "").strip()
        if not clean_name:
            raise ValueError("Contract name is required.")

        with self._lock:
            source = self._driver.get_contract(clean_name)

        if source is None:
            raise ValueError(f"Contract '{clean_name}' is not deployed.")

        exports = self._parse_exports(source)
        return ContractDetails(
            name=clean_name,
            source=source,
            exports=exports,
        )

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

    @staticmethod
    def _parse_exports(source: str) -> List[ContractExportInfo]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        exports: List[ContractExportInfo] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and any(
                _is_export_decorator(dec) for dec in node.decorator_list
            ):
                doc = ast.get_docstring(node) or ""
                exports.append(
                    ContractExportInfo(
                        name=node.name,
                        docstring=doc.strip(),
                    )
                )
        return exports


contracting_service = ContractingService()
