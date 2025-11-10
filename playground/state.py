from __future__ import annotations

import ast
import json
import time
from http.cookies import SimpleCookie
from typing import List
from urllib.parse import quote

import reflex as rx
from reflex.config import get_config

from .defaults import DEFAULT_CONTRACT, DEFAULT_CONTRACT_NAME, DEFAULT_KWARGS_INPUT
from .services import (
    ContractDetails,
    ContractExportInfo,
    DEFAULT_ENVIRONMENT,
    ENVIRONMENT_FIELDS,
    SESSION_COOKIE_NAME,
    SessionNotFoundError,
    SessionRepository,
    lint_contract as run_lint,
    session_runtime,
)
from .services.environment import stringify_environment_value

ENVIRONMENT_FIELD_KEYS = [field["key"] for field in ENVIRONMENT_FIELDS]
SESSION_UI_FIELDS = [
    "code_editor",
    "contract_name",
    "kwargs_input",
    "load_view_decompiled",
    "expanded_panel",
    "selected_contract",
    "load_selected_contract",
    "function_name",
    "show_internal_state",
]


class PlaygroundState(rx.State):
    """Global Reflex state powering the playground UI."""

    code_editor: str = DEFAULT_CONTRACT
    code_editor_revision: int = 0
    contract_name: str = DEFAULT_CONTRACT_NAME
    deploy_message: str = ""
    deploy_is_error: bool = False

    expert_message: str = ""
    expert_is_error: bool = False
    show_internal_state: bool = False
    environment_editor: dict[str, str] = {
        key: DEFAULT_ENVIRONMENT.get(key, "") for key in ENVIRONMENT_FIELD_KEYS
    }
    session_id: str = ""
    session_error: str = ""
    resume_session_input: str = ""
    _last_ui_snapshot_ts: float = 0.0

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

    kwargs_input: str = DEFAULT_KWARGS_INPUT
    run_result: str = ""
    state_dump: str = "{}"
    _saved_code_snapshot: str = DEFAULT_CONTRACT

    def on_load(self):
        session_id = self._cookie_session_id()
        if not session_id:
            self.session_error = "Session cookie missing. Issuing a fresh session."
            return [rx.redirect(self._session_route_url("new"))]
        self.session_id = session_id
        try:
            metadata = session_runtime.ensure_exists(session_id)
        except SessionNotFoundError:
            self.session_error = "Session not found. Creating a new one."
            return [rx.redirect(self._session_route_url("new"))]

        self._apply_ui_state(metadata.ui_state or {})
        env_snapshot = session_runtime.get_environment_snapshot(session_id)
        self.environment_editor = {
            key: env_snapshot.get(key, "")
            for key in ENVIRONMENT_FIELD_KEYS
        }
        self.session_error = ""
        self._last_ui_snapshot_ts = time.time()
        return [
            type(self).refresh_contracts,
            type(self).refresh_state,
            type(self).refresh_environment,
        ]

    def _cookie_session_id(self) -> str:
        header = getattr(self.router.headers, "cookie", "") or ""
        if not header:
            return ""
        jar = SimpleCookie()
        try:
            jar.load(header)
        except Exception:
            return ""
        morsel = jar.get(SESSION_COOKIE_NAME)
        return (morsel.value or "").strip() if morsel else ""

    def _apply_ui_state(self, snapshot: dict[str, object]):
        if not snapshot:
            return
        pending_editor_value = snapshot.get("code_editor")
        for field in SESSION_UI_FIELDS:
            if field == "code_editor" or field not in snapshot:
                continue
            setattr(self, field, snapshot[field])

        if pending_editor_value is not None:
            self._hydrate_code_editor(str(pending_editor_value))

    def _hydrate_code_editor(self, value: str, *, force_refresh: bool = False):
        normalized = value or ""
        if not force_refresh and normalized == self.code_editor:
            self._saved_code_snapshot = normalized
            return
        self.code_editor = normalized
        self._saved_code_snapshot = normalized
        self.code_editor_revision += 1

    def _save_session(self, include_code: bool = False):
        if not self.session_id:
            return
        payload = {}
        for field in SESSION_UI_FIELDS:
            if field == "code_editor":
                payload[field] = self.code_editor if include_code else self._saved_code_snapshot
            else:
                payload[field] = getattr(self, field)
        session_runtime.save_ui_state(self.session_id, payload)
        if include_code:
            self._saved_code_snapshot = self.code_editor

    def _require_session(self) -> str | None:
        if not self.session_id:
            self.session_error = "Session unavailable. Refresh the page to rehydrate."
            return None
        return self.session_id

    def _frontend_origin(self) -> str:
        url = getattr(self.router, "url", None)
        if url is not None:
            origin = getattr(url, "origin", "") or ""
            if origin:
                return origin.rstrip("/")
        header_origin = getattr(self.router.headers, "origin", "") or ""
        if header_origin:
            return header_origin.rstrip("/")
        config = get_config()
        if config.deploy_url:
            return config.deploy_url.rstrip("/")
        return ""

    def _session_route_url(self, suffix: str) -> str:
        config = get_config()
        base = (config.api_url or "").rstrip("/")
        path = suffix.lstrip("/")
        next_url = self._frontend_origin()
        query = ""
        if next_url:
            encoded = quote(next_url, safe=":/?#[]@!$&'()*+,;=%")
            query = f"?next={encoded}"
        if not base:
            return f"/sessions/{path}{query}"
        return f"{base}/sessions/{path}{query}"

    def copy_session_id(self):
        if not self.session_id:
            return [rx.toast.error("Session unavailable. Reload the page.")]
        return [
            rx.set_clipboard(self.session_id),
            rx.toast.success("Session ID copied."),
        ]

    def start_new_session(self):
        return [rx.redirect(self._session_route_url("new"), is_external=True)]

    def update_resume_session_input(self, value: str):
        self.resume_session_input = (value or "").strip().lower()

    def resume_session(self):
        target = (self.resume_session_input or "").strip().lower()
        if not target:
            self.session_error = "Enter a session ID to resume."
            return [rx.toast.error(self.session_error)]
        if not SessionRepository.is_valid_session_id(target):
            self.session_error = "Session ID must be a UUID4 hex string."
            return [rx.toast.error(self.session_error)]
        if not session_runtime.session_exists(target):
            self.session_error = "Session not found."
            return [rx.toast.error(self.session_error)]
        self.session_error = ""
        return [rx.redirect(self._session_route_url(target), is_external=True)]

    def save_code_draft(self):
        session_id = self._require_session()
        if not session_id:
            return []
        self._save_session(include_code=True)
        return [rx.toast.success("Draft saved.")]

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
            self.kwargs_input = DEFAULT_KWARGS_INPUT
            self.run_result = ""
        return [type(self).refresh_functions]

    def change_selected_function(self, value: str):
        self.function_name = value
        self.run_result = ""
        self.prefill_kwargs_for_current_function(force=True)

    def refresh_contracts(self):
        session_id = self._require_session()
        if not session_id:
            return []
        contracts = session_runtime.list_contracts(session_id)
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
            self.kwargs_input = DEFAULT_KWARGS_INPUT

        if not self.load_selected_contract or self.load_selected_contract not in contracts:
            self.load_selected_contract = contracts[0]

        return [type(self).refresh_functions, type(self).refresh_loaded_contract]

    def refresh_functions(self):
        session_id = self._require_session()
        if not session_id:
            return []
        if not self.selected_contract:
            self.available_functions = []
            self.function_name = ""
            self.function_required_params = {}
            return

        exports: List[ContractExportInfo] = session_runtime.get_export_metadata(session_id, self.selected_contract)
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
        session_id = self._require_session()
        if not session_id:
            return []
        if not self.load_selected_contract:
            self.loaded_contract_code = ""
            self.loaded_contract_decompiled = ""
            return []

        try:
            details: ContractDetails = session_runtime.get_contract_details(session_id, self.load_selected_contract)
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

    def handle_fullscreen_keydown(self, event):
        """Handle keyboard events in fullscreen mode - exit on ESC key."""
        # Event can be a string or dict depending on Reflex version
        key = event if isinstance(event, str) else event.get("key", "")
        if key == "Escape":
            self.expanded_panel = ""

    def prefill_kwargs_for_current_function(self, force: bool = False):
        if not self.function_name:
            return
        required = self.function_required_params.get(self.function_name, [])
        if not required:
            if force or self.kwargs_input.strip() != DEFAULT_KWARGS_INPUT:
                self.kwargs_input = DEFAULT_KWARGS_INPUT
            return
        # Only seed the editor if it is still empty or in the default form.
        current = self.kwargs_input.strip()
        if force or current in ("", DEFAULT_KWARGS_INPUT):
            payload = {name: "" for name in required}
            self.kwargs_input = json.dumps(payload, indent=2)

    def confirm_clear_state(self):
        session_id = self._require_session()
        if not session_id:
            return []
        try:
            metadata = session_runtime.reset_state(session_id)
        except Exception as exc:
            return [rx.toast.error(f"Failed to clear state: {exc}")]

        env = metadata.environment

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
        self.kwargs_input = DEFAULT_KWARGS_INPUT
        self.run_result = ""
        self.state_is_editing = False
        self.state_dump = "{}"
        self.state_editor = "{}"
        self.lint_results = []
        self._hydrate_code_editor(DEFAULT_CONTRACT, force_refresh=True)
        self.contract_name = DEFAULT_CONTRACT_NAME
        self.environment_editor = {
            key: stringify_environment_value(env.get(key))
            for key in ENVIRONMENT_FIELD_KEYS
        }
        self._save_session(include_code=True)

        return [
            rx.toast.success("All contracts and state cleared."),
            type(self).refresh_environment,
            type(self).refresh_contracts,
            type(self).refresh_state,
        ]

    def export_state(self):
        session_id = self._require_session()
        if not session_id:
            return []
        data = session_runtime.dump_state(session_id, show_internal=True)
        return [
            rx.download(
                data=data,
                filename="contract_state.json",
            )
        ]

    async def import_state(self, files: list[rx.UploadFile]):
        if not files:
            return [rx.toast.info("Select a JSON export to import.")]

        session_id = self._require_session()
        if not session_id:
            return []

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
            session_runtime.apply_state_snapshot(session_id, payload)
        except Exception as exc:
            return [rx.toast.error(f"Failed to import state: {exc}")]
        self._save_session()

        return [
            rx.toast.success("State imported."),
            type(self).refresh_state,
            type(self).refresh_contracts,
        ]

    def remove_selected_contract(self):
        target = self.load_selected_contract or self.selected_contract
        if not target:
            return [rx.toast.info("Select a contract to remove.")]

        session_id = self._require_session()
        if not session_id:
            return []

        try:
            session_runtime.remove_contract(session_id, target)
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
        self._save_session()

        return [
            rx.toast.success(f"Contract '{target}' removed."),
            type(self).refresh_contracts,
            type(self).refresh_state,
        ]

    def refresh_state(self):
        session_id = self._require_session()
        if not session_id:
            return []
        snapshot = session_runtime.dump_state(session_id, self.show_internal_state)
        self.state_dump = snapshot
        if not self.state_is_editing:
            self.state_editor = snapshot

    def refresh_environment(self):
        session_id = self._require_session()
        if not session_id:
            return []
        env = session_runtime.get_environment(session_id)
        self.environment_editor = {
            key: stringify_environment_value(env.get(key))
            for key in ENVIRONMENT_FIELD_KEYS
        }

    def deploy_contract(self):
        session_id = self._require_session()
        if not session_id:
            return []
        try:
            session_runtime.deploy(session_id, self.contract_name, self.code_editor)
        except Exception as exc:
            self.deploy_is_error = True
            self.deploy_message = f"Deploy failed: {exc}"
            return [rx.toast.error(self.deploy_message)]

        self.deploy_is_error = False
        self.deploy_message = f"Contract '{self.contract_name}' deployed successfully."
        self.selected_contract = self.contract_name
        self.load_selected_contract = self.contract_name
        self.kwargs_input = DEFAULT_KWARGS_INPUT
        self._save_session(include_code=True)

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
        session_id = self._require_session()
        if not session_id:
            return []
        try:
            if current.strip() == "":
                session_runtime.remove_environment_var(session_id, key)
                message = f"Environment['{key}'] cleared."
                toast = rx.toast.info(message)
            else:
                session_runtime.set_environment_var(session_id, key, current)
                message = f"Environment['{key}'] updated."
                toast = rx.toast.success(message)
        except Exception as exc:
            self.expert_is_error = True
            self.expert_message = f"Failed to set environment['{key}']: {exc}"
            return [rx.toast.error(self.expert_message)]

        self.expert_is_error = False
        self.expert_message = message
        self._save_session()
        return [toast, type(self).refresh_environment]

    def reset_environment_value(self, key):
        if isinstance(key, dict):
            key = key.get("value", "")
        if not key:
            return []
        session_id = self._require_session()
        if not session_id:
            return []
        session_runtime.remove_environment_var(session_id, key)
        self.environment_editor[key] = DEFAULT_ENVIRONMENT.get(key, "")
        self.expert_is_error = False
        self.expert_message = f"Environment['{key}'] cleared."
        self._save_session()
        return [rx.toast.info(self.expert_message), type(self).refresh_environment]

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

        session_id = self._require_session()
        if not session_id:
            return []
        try:
            session_runtime.apply_state_snapshot(session_id, data)
        except Exception as exc:
            return [rx.toast.error(f"Failed to update state: {exc}")]

        self.state_is_editing = False
        self.refresh_state()
        self._save_session()
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

        session_id = self._require_session()
        if not session_id:
            return []
        try:
            call_result = session_runtime.call(session_id, self.selected_contract, self.function_name, kwargs)
        except Exception as exc:
            self.run_result = f"Execution failed: {exc}"
            return [rx.toast.error(self.run_result)]

        self.run_result = call_result.as_string()
        return [
            rx.toast.success("Execution succeeded."),
            type(self).refresh_state,
            type(self).refresh_contracts,
        ]
