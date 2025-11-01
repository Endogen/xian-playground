from __future__ import annotations

import ast
import json
from datetime import datetime as PyDatetime
from typing import List

import reflex as rx

from contracting.stdlib.bridge.time import Datetime as ContractingDatetime

from .services import contracting_service, ENVIRONMENT_FIELDS

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
    contract_name: str = "demo_token"
    deploy_message: str = ""
    deploy_is_error: bool = False

    expert_message: str = ""
    expert_is_error: bool = False
    show_internal_state: bool = False
    environment_editor: dict[str, str] = {key: "" for key in ENVIRONMENT_FIELD_KEYS}

    deployed_contracts: List[str] = []
    selected_contract: str = ""
    available_functions: List[str] = []
    function_name: str = ""

    kwargs_input: str = "{}"
    run_result: str = ""
    state_dump: str = "{}"

    def on_load(self):
        env = contracting_service.get_environment()
        self.environment_editor = {
            key: self._stringify_env_value(env.get(key))
            for key in ENVIRONMENT_FIELD_KEYS
        }
        return [
            type(self).refresh_contracts,
            type(self).refresh_state,
            type(self).refresh_environment,
        ]

    def update_code(self, value: str):
        self.code_editor = value

    def update_contract_name(self, value: str):
        self.contract_name = value

    def update_kwargs(self, value: str):
        self.kwargs_input = value

    def change_selected_contract(self, value: str):
        self.selected_contract = value
        return [type(self).refresh_functions]

    def change_selected_function(self, value: str):
        self.function_name = value

    def refresh_contracts(self):
        contracts = contracting_service.list_contracts()
        self.deployed_contracts = contracts

        if not contracts:
            self.selected_contract = ""
            self.available_functions = []
            self.function_name = ""
            return []

        if self.selected_contract not in contracts:
            self.selected_contract = contracts[0]

        return [type(self).refresh_functions]

    def refresh_functions(self):
        if not self.selected_contract:
            self.available_functions = []
            self.function_name = ""
            return

        functions = contracting_service.list_functions(self.selected_contract)
        self.available_functions = functions

        if not functions:
            self.function_name = ""
        elif self.function_name not in functions:
            self.function_name = functions[0]

    def refresh_state(self):
        self.state_dump = contracting_service.dump_state(self.show_internal_state)

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
            return

        self.deploy_is_error = False
        self.deploy_message = f"Contract '{self.contract_name}' deployed successfully."
        self.selected_contract = self.contract_name

        return [
            type(self).refresh_contracts,
            type(self).refresh_state,
            type(self).refresh_environment,
        ]

    def set_show_internal_state(self, value):
        if isinstance(value, dict):
            value = value.get("value", False)
        self.show_internal_state = bool(value)
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
            else:
                contracting_service.set_environment_var(key, current)
                message = f"Environment['{key}'] updated."
        except Exception as exc:
            self.expert_is_error = True
            self.expert_message = f"Failed to set environment['{key}']: {exc}"
            return []

        self.expert_is_error = False
        self.expert_message = message
        return [type(self).refresh_environment]

    def reset_environment_value(self, key):
        if isinstance(key, dict):
            key = key.get("value", "")
        if not key:
            return []
        contracting_service.remove_environment_var(key)
        self.environment_editor[key] = ""
        self.expert_is_error = False
        self.expert_message = f"Environment['{key}'] cleared."
        return [type(self).refresh_environment]

    @staticmethod
    def _stringify_env_value(value: object) -> str:
        if isinstance(value, ContractingDatetime):
            return value._datetime.isoformat()
        if isinstance(value, PyDatetime):
            return value.isoformat()
        if value is None:
            return ""
        return str(value)

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
            return

        try:
            call_result = contracting_service.call(self.selected_contract, self.function_name, kwargs)
        except Exception as exc:
            self.run_result = f"Execution failed: {exc}"
            return

        self.run_result = call_result.as_string()
        return [type(self).refresh_state]
