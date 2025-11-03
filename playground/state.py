from __future__ import annotations

import ast
import json
from datetime import datetime as PyDatetime
from typing import List

import reflex as rx

from contracting.stdlib.bridge.time import Datetime as ContractingDatetime

from .services import (
    ContractDetails,
    contracting_service,
    ContractExportInfo,
    ENVIRONMENT_FIELDS,
    DEFAULT_ENVIRONMENT,
    lint_contract as run_lint,
)

ENVIRONMENT_FIELD_KEYS = [field["key"] for field in ENVIRONMENT_FIELDS]


DEFAULT_CONTRACT = """\
balances = Hash(default_value=0)


@construct
def seed():
    balances['treasury'] = 1_000


@export
def transfer(to: str, amount: int):
    assert amount > 0, 'Amount must be positive.'
    assert balances[ctx.caller] >= amount, 'Insufficient balance.'

    balances[ctx.caller] -= amount
    balances[to] += amount


@export
def balance_of(account: str):
    return balances[account]
"""


class PlaygroundState(rx.State):
    """Global Reflex state powering the playground UI."""

    code_editor: str = DEFAULT_CONTRACT
    contract_name: str = "con_demo_token"
    deploy_message: str = ""
    deploy_is_error: bool = False

    expert_message: str = ""
    expert_is_error: bool = False
    show_internal_state: bool = False
    environment_editor: dict[str, str] = {
        key: DEFAULT_ENVIRONMENT.get(key, "") for key in ENVIRONMENT_FIELD_KEYS
    }

    state_is_editing: bool = False
    state_editor: str = ""
    lint_results: List[str] = []
    linting: bool = False

    deployed_contracts: List[str] = []
    selected_contract: str = ""
    available_functions: List[str] = []
    function_name: str = ""

    load_selected_contract: str = ""
    loaded_contract_code: str = ""
    loaded_contract_decompiled: str = ""
    function_required_params: dict[str, List[str]] = {}
    load_view_decompiled: bool = True
    expanded_panel: str = ""

    kwargs_input: str = "{}"
    run_result: str = ""
    state_dump: str = "{}"

    def on_load(self):
        env = contracting_service.get_environment()
        self.environment_editor = {
            key: self._stringify_env_value(env.get(key))
            for key in ENVIRONMENT_FIELD_KEYS
        }
        if self.deployed_contracts:
            if not self.load_selected_contract:
                self.load_selected_contract = self.deployed_contracts[0]
        self.state_editor = self.state_dump
        return [
            type(self).refresh_contracts,
            type(self).refresh_state,
            type(self).refresh_environment,
        ]

    def update_code(self, value: str):
        self.code_editor = value or ""
        self.lint_results = []

    def update_contract_name(self, value: str):
        self.contract_name = value

    def update_kwargs(self, value: str):
        self.kwargs_input = value

    def change_selected_contract(self, value: str):
        if value != self.selected_contract:
            self.selected_contract = value
            self.kwargs_input = "{}"
        return [type(self).refresh_functions]

    def change_selected_function(self, value: str):
        self.function_name = value
        self.run_result = ""
        self.prefill_kwargs_for_current_function(force=True)

    def refresh_contracts(self):
        contracts = contracting_service.list_contracts()
        self.deployed_contracts = contracts

        if not contracts:
            self.selected_contract = ""
            self.available_functions = []
            self.function_name = ""
            self.load_selected_contract = ""
            self.loaded_contract_code = ""
            self.loaded_contract_decompiled = ""
            self.function_required_params = {}
            return []

        if self.selected_contract not in contracts:
            self.selected_contract = contracts[0]
            self.kwargs_input = "{}"

        if not self.load_selected_contract or self.load_selected_contract not in contracts:
            self.load_selected_contract = contracts[0]

        return [type(self).refresh_functions, type(self).refresh_loaded_contract]

    def refresh_functions(self):
        if not self.selected_contract:
            self.available_functions = []
            self.function_name = ""
            self.function_required_params = {}
            return

        exports: List[ContractExportInfo] = contracting_service.get_export_metadata(self.selected_contract)
        required_map = {
            export.name: [
                param.name for param in (export.parameters or []) if param.required
            ]
            for export in exports
        }
        self.function_required_params = required_map

        functions = sorted(required_map.keys())
        self.available_functions = functions

        if not functions:
            self.function_name = ""
        elif self.function_name not in functions:
            self.function_name = functions[0]

        self.prefill_kwargs_for_current_function()

    def change_loaded_contract(self, value: str):
        self.load_selected_contract = value
        return [type(self).refresh_loaded_contract]

    def refresh_loaded_contract(self):
        if not self.load_selected_contract:
            self.loaded_contract_code = ""
            self.loaded_contract_decompiled = ""
            return []

        try:
            details: ContractDetails = contracting_service.get_contract_details(self.load_selected_contract)
        except Exception as exc:
            self.loaded_contract_code = ""
            self.loaded_contract_decompiled = ""
            return [rx.toast.error(f"Failed to load contract '{self.load_selected_contract}': {exc}")]

        self.loaded_contract_code = details.source
        self.loaded_contract_decompiled = details.decompiled_source
        return []

    def toggle_load_view(self):
        self.load_view_decompiled = not self.load_view_decompiled

    def toggle_panel(self, panel_id: str):
        target = (panel_id or "").strip()
        if not target:
            return
        self.expanded_panel = "" if self.expanded_panel == target else target

    def prefill_kwargs_for_current_function(self, force: bool = False):
        if not self.function_name:
            return
        required = self.function_required_params.get(self.function_name, [])
        if not required:
            if force or self.kwargs_input.strip() != "{}":
                self.kwargs_input = "{}"
            return
        # Only seed the editor if it is still empty or in the default form.
        current = self.kwargs_input.strip()
        if force or current in ("", "{}"):
            payload = {name: "" for name in required}
            self.kwargs_input = json.dumps(payload, indent=2)

    def confirm_clear_state(self):
        try:
            contracting_service.reset_state()
        except Exception as exc:
            return [rx.toast.error(f"Failed to clear state: {exc}")]

        env = contracting_service.get_environment()

        self.deployed_contracts = []
        self.selected_contract = ""
        self.available_functions = []
        self.function_name = ""
        self.function_required_params = {}
        self.load_selected_contract = ""
        self.loaded_contract_code = ""
        self.loaded_contract_decompiled = ""
        self.load_view_decompiled = True
        self.expanded_panel = ""
        self.kwargs_input = "{}"
        self.run_result = ""
        self.state_is_editing = False
        self.state_dump = "{}"
        self.state_editor = "{}"
        self.lint_results = []
        self.code_editor = DEFAULT_CONTRACT
        self.contract_name = "con_demo_token"
        self.environment_editor = {
            key: self._stringify_env_value(env.get(key))
            for key in ENVIRONMENT_FIELD_KEYS
        }

        return [
            rx.toast.success("All contracts and state cleared."),
            type(self).refresh_environment,
            type(self).refresh_contracts,
            type(self).refresh_state,
        ]

    def export_state(self):
        data = contracting_service.dump_state(show_internal=True)
        return [
            rx.download(
                data=data,
                filename="contract_state.json",
            )
        ]

    async def import_state(self, files: list[rx.UploadFile]):
        if not files:
            return [rx.toast.info("Select a JSON export to import.")]

        file = files[0]
        try:
            content = await file.read()
        except Exception as exc:
            return [rx.toast.error(f"Failed to read import: {exc}")]
        finally:
            await file.close()

        if isinstance(content, bytes):
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                return [rx.toast.error("Import file must be UTF-8 encoded JSON.")]
        else:
            text = str(content)

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            return [rx.toast.error(f"Invalid JSON: {exc}")]

        try:
            contracting_service.apply_state_snapshot(payload)
        except Exception as exc:
            return [rx.toast.error(f"Failed to import state: {exc}")]

        return [
            rx.toast.success("State imported."),
            type(self).refresh_state,
            type(self).refresh_contracts,
        ]

    def remove_selected_contract(self):
        target = self.load_selected_contract or self.selected_contract
        if not target:
            return [rx.toast.info("Select a contract to remove.")]

        try:
            contracting_service.remove_contract(target)
        except Exception as exc:
            return [rx.toast.error(f"Failed to remove contract '{target}': {exc}")]

        if self.selected_contract == target:
            self.selected_contract = ""
            self.available_functions = []
            self.function_name = ""
            self.kwargs_input = "{}"

        if self.load_selected_contract == target:
            self.load_selected_contract = ""
            self.loaded_contract_code = ""
            self.loaded_contract_decompiled = ""
        if self.expanded_panel == target:
            self.expanded_panel = ""

        self.run_result = ""

        return [
            rx.toast.success(f"Contract '{target}' removed."),
            type(self).refresh_contracts,
            type(self).refresh_state,
        ]

    def refresh_state(self):
        snapshot = contracting_service.dump_state(self.show_internal_state)
        self.state_dump = snapshot
        if not self.state_is_editing:
            self.state_editor = snapshot

    def refresh_environment(self):
        env = contracting_service.get_environment()
        self.environment_editor = {
            key: self._stringify_env_value(env.get(key))
            for key in ENVIRONMENT_FIELD_KEYS
        }

    def deploy_contract(self):
        try:
            contracting_service.deploy(self.contract_name, self.code_editor)
        except Exception as exc:
            self.deploy_is_error = True
            self.deploy_message = f"Deploy failed: {exc}"
            return [rx.toast.error(self.deploy_message)]

        self.deploy_is_error = False
        self.deploy_message = f"Contract '{self.contract_name}' deployed successfully."
        self.selected_contract = self.contract_name
        self.load_selected_contract = self.contract_name

        events = [
            rx.toast.success(self.deploy_message),
            type(self).refresh_contracts,
            type(self).refresh_state,
            type(self).refresh_environment,
            type(self).refresh_loaded_contract,
        ]
        return events

    def set_show_internal_state(self, value):
        if isinstance(value, dict):
            value = value.get("value", False)
        self.show_internal_state = bool(value)
        return [type(self).refresh_state]

    def toggle_show_internal_state(self):
        self.show_internal_state = not self.show_internal_state
        return [type(self).refresh_state]

    def edit_environment_value(self, key: str, value):
        if isinstance(key, dict):
            key = key.get("value", "")
        if isinstance(value, dict):
            value = value.get("value", "")
        if not key:
            return
        if key in self.environment_editor:
            self.environment_editor[key] = value

    def apply_environment_value(self, key):
        if isinstance(key, dict):
            key = key.get("value", "")
        if not key:
            self.expert_is_error = True
            self.expert_message = "No environment key selected."
            return []
        current = self.environment_editor.get(key, "")
        try:
            if current.strip() == "":
                contracting_service.remove_environment_var(key)
                message = f"Environment['{key}'] cleared."
                toast = rx.toast.info(message)
            else:
                contracting_service.set_environment_var(key, current)
                message = f"Environment['{key}'] updated."
                toast = rx.toast.success(message)
        except Exception as exc:
            self.expert_is_error = True
            self.expert_message = f"Failed to set environment['{key}']: {exc}"
            return [rx.toast.error(self.expert_message)]

        self.expert_is_error = False
        self.expert_message = message
        return [toast, type(self).refresh_environment]

    def reset_environment_value(self, key):
        if isinstance(key, dict):
            key = key.get("value", "")
        if not key:
            return []
        contracting_service.remove_environment_var(key)
        self.environment_editor[key] = DEFAULT_ENVIRONMENT.get(key, "")
        self.expert_is_error = False
        self.expert_message = f"Environment['{key}'] cleared."
        return [rx.toast.info(self.expert_message), type(self).refresh_environment]

    @staticmethod
    def _stringify_env_value(value: object) -> str:
        if isinstance(value, ContractingDatetime):
            return value._datetime.isoformat()
        if isinstance(value, PyDatetime):
            return value.isoformat()
        if value is None:
            return ""
        return str(value)

    def update_state_editor(self, value: str):
        self.state_editor = value

    def cancel_state_editing(self):
        self.state_is_editing = False
        self.state_editor = self.state_dump
        return []

    def toggle_state_editor(self):
        if not self.state_is_editing:
            self.state_editor = self.state_dump
            self.state_is_editing = True
            return []

        try:
            data = json.loads(self.state_editor)
        except json.JSONDecodeError as exc:
            return [rx.toast.error(f"Invalid JSON: {exc}")]

        try:
            contracting_service.apply_state_snapshot(data)
        except Exception as exc:
            return [rx.toast.error(f"Failed to update state: {exc}")]

        self.state_is_editing = False
        self.refresh_state()
        return [rx.toast.success("State updated.")]

    def lint_contract(self):
        if self.linting:
            return []

        self.linting = True
        try:
            raw_results = run_lint(self.code_editor)
        except Exception as exc:
            self.linting = False
            self.lint_results = []
            return [rx.toast.error(f"Lint failed: {exc}")]

        self.linting = False
        formatted: list[str] = []
        for result in raw_results:
            if isinstance(result, dict):
                position = result.get("position") or {}
                line = position.get("line")
                column = position.get("column")
                message = result.get("message", "")
                location = ""
                if line is not None:
                    location = f"Line {line + 1}"
                    if column is not None:
                        location += f", Col {column + 1}"
                    location += ": "
                formatted.append(f"{location}{message}")
            else:
                formatted.append(str(result))

        self.lint_results = formatted

        if formatted:
            return [
                rx.toast.warning(f"Found {len(formatted)} issue(s)."),
            ]
        return [rx.toast.success("No lint issues found.")]

    def _parse_kwargs(self) -> dict:
        raw = self.kwargs_input.strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            try:
                data = ast.literal_eval(raw)
            except Exception as exc:
                raise ValueError(f"Cannot parse kwargs: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("Kwargs must evaluate to a dictionary.")
        return data

    def run_contract(self):
        if not self.selected_contract:
            self.run_result = "Select a deployed contract first."
            return
        if not self.function_name:
            self.run_result = "Select a function to execute."
            return

        try:
            kwargs = self._parse_kwargs()
        except ValueError as exc:
            self.run_result = str(exc)
            return [rx.toast.error(self.run_result)]

        try:
            call_result = contracting_service.call(self.selected_contract, self.function_name, kwargs)
        except Exception as exc:
            self.run_result = f"Execution failed: {exc}"
            return [rx.toast.error(self.run_result)]

        self.run_result = call_result.as_string()
        return [
            rx.toast.success("Execution succeeded."),
            type(self).refresh_state,
            type(self).refresh_contracts,
        ]
