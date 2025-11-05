from __future__ import annotations

from typing import Any, Dict

import reflex as rx
from reflex.components.radix.themes.components.badge import Badge
from reflex.config import get_config
from starlette.requests import Request
from starlette.responses import RedirectResponse
from urllib.parse import unquote

from .components import MonacoEditor
from .services import ENVIRONMENT_FIELDS, SessionRepository, session_runtime
from .session_middleware import SessionCookieMiddleware, issue_session_cookie
from .state import PlaygroundState


# Modern dark theme color scheme inspired by blockchain explorers
COLORS = {
    "bg_primary": "#0a0a0b",
    "bg_secondary": "#151518",
    "bg_tertiary": "#1a1a1d",
    "border": "#27272a",
    "border_subtle": "#1f1f23",
    "text_primary": "#ffffff",
    "text_secondary": "#a1a1aa",
    "text_muted": "#71717a",
    "accent_purple": "#8b5cf6",
    "accent_blue": "#3b82f6",
    "accent_cyan": "#06b6d4",
    "success": "#10b981",
    "warning": "#f59e0b",
    "error": "#ef4444",
}


def card(
    *children,
    **kwargs,
) -> rx.Component:
    """Modern card component with dark theme styling."""
    default_style = {
        "background": COLORS["bg_secondary"],
        "border": f"1px solid {COLORS['border']}",
        "border_radius": "12px",
        "padding": "24px",
        "display": "flex",
        "flex_direction": "column",
        "gap": "16px",
        "width": "100%",
        "box_shadow": "0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)",
        "max_height": "720px",
        "overflow": "hidden",
    }
    if kwargs.get("flex"):
        default_style.pop("max_height", None)
        default_style.pop("overflow", None)
    return rx.box(*children, **{**default_style, **kwargs})


def panel_expand_icon(panel_id: str) -> rx.Component:
    is_expanded = PlaygroundState.expanded_panel == panel_id
    icon_color = COLORS["text_secondary"]

    icon = rx.cond(
        is_expanded,
        rx.icon(tag="minimize_2", size=18, color=icon_color),
        rx.icon(tag="maximize_2", size=18, color=icon_color),
    )

    return rx.tooltip(
        rx.box(
            icon,
            on_click=lambda _: PlaygroundState.toggle_panel(panel_id),
            cursor="pointer",
            padding="6px",
            border_radius="999px",
            background=COLORS["bg_tertiary"],
            _hover={"background": COLORS["bg_secondary"]},
        ),
        content=rx.cond(
            is_expanded,
            "Exit fullscreen",
            "Toggle fullscreen",
        ),
        delay_duration=200,
    )


def section_header(
    title: str,
    description: str = "",
    panel_id: str | None = None,
    trailing: rx.Component | None = None,
    icon: str | None = None,
) -> rx.Component:
    """Section header with optional fullscreen icon and trailing controls."""

    heading_contents = []
    if icon:
        heading_contents.append(
            rx.icon(
                tag=icon,
                size=18,
                color=COLORS["accent_cyan"],
            )
        )
    heading_contents.append(
        rx.heading(
            title,
            size="5",
            color=COLORS["text_primary"],
            font_weight="600",
        )
    )

    title_row = rx.hstack(
        rx.hstack(
            *heading_contents,
            align_items="center",
            gap="8px",
        ),
        rx.spacer(),
        rx.cond(
            trailing is not None,
            trailing,
            rx.fragment(),
        ),
        rx.cond(
            panel_id is not None,
            panel_expand_icon(panel_id),
            rx.fragment(),
        ),
        align_items="center",
        width="100%",
        gap="12px",
    )

    description_el = rx.cond(
        description != "",
        rx.text(
            description,
            color=COLORS["text_secondary"],
            size="2",
            line_height="1.6",
        ),
        rx.fragment(),
    )

    return rx.vstack(
        title_row,
        description_el,
        gap="8px",
        align_items="start",
        width="100%",
    )


def code_viewer(value: str, language: str, empty_message: str, font_size: str = "14px") -> rx.Component:
    return rx.cond(
        value == "",
        rx.text(
            empty_message,
            color=COLORS["text_secondary"],
            font_style="italic",
            font_size="14px",
        ),
        rx.code_block(
            value,
            language=language,
            wrap_lines=True,
            width="100%",
            style={
                "height": "100%",
                "margin": "0",
                "fontSize": font_size,
            },
        ),
    )

def styled_input(**kwargs) -> rx.Component:
    """Styled input field with dark theme."""
    default_style = {
        "background": COLORS["bg_tertiary"],
        "border": f"1px solid {COLORS['border']}",
        "border_radius": "8px",
        "color": COLORS["text_primary"],
        "font_size": "14px",
        "_focus": {
            "border_color": COLORS["accent_cyan"],
            "outline": "none",
        },
    }
    return rx.input(**{**default_style, **kwargs})


def styled_text_area(**kwargs) -> rx.Component:
    """Styled text area with dark theme."""
    default_style = {
        "background": COLORS["bg_tertiary"],
        "border": f"1px solid {COLORS['border']}",
        "border_radius": "8px",
        "color": COLORS["text_primary"],
        "font_size": "14px",
        "resize": "vertical",
        "_focus": {
            "border_color": COLORS["accent_cyan"],
            "outline": "none",
        },
    }
    return rx.text_area(**{**default_style, **kwargs})


def session_panel() -> rx.Component:
    """Session controls and resume form."""
    return card(
        section_header(
            "Session",
            "Every browser session gets its own isolated runtime. Copy the ID to save it or resume one you've stored.",
            icon="shield",
        ),
        rx.vstack(
            rx.hstack(
                rx.code(
                    rx.cond(
                        PlaygroundState.session_id != "",
                        PlaygroundState.session_id,
                        "Pending...",
                    ),
                    color=COLORS["accent_cyan"],
                    font_size="13px",
                    font_family="'Fira Code', 'Monaco', 'Courier New', monospace",
                    padding="6px 10px",
                    background=COLORS["bg_tertiary"],
                    border_radius="6px",
                    letter_spacing="-0.01em",
                ),
                styled_button(
                    "Copy ID",
                    color_scheme="cyan",
                    on_click=PlaygroundState.copy_session_id,
                ),
                styled_input(
                    placeholder="Enter an existing session ID (UUID4 format)",
                    value=PlaygroundState.resume_session_input,
                    on_change=PlaygroundState.update_resume_session_input,
                    font_family="'Fira Code', 'Monaco', 'Courier New', monospace",
                    font_size="13px",
                    flex="1",
                    min_width="320px",
                ),
                styled_button(
                    "Resume",
                    color_scheme="blue",
                    on_click=PlaygroundState.resume_session,
                ),
                styled_button(
                    "New Session",
                    color_scheme="purple",
                    on_click=PlaygroundState.start_new_session,
                ),
                align_items="center",
                width="100%",
                gap="12px",
            ),
            rx.cond(
                PlaygroundState.session_error != "",
                rx.text(
                    PlaygroundState.session_error,
                    color=COLORS["warning"],
                    size="1",
                ),
                rx.fragment(),
            ),
            spacing="3",
            width="100%",
        ),
    )


def styled_button(text: str, color_scheme: str = "blue", **kwargs) -> rx.Component:
    """Styled button with modern appearance."""
    color_map = {
        "purple": COLORS["accent_purple"],
        "blue": COLORS["accent_blue"],
        "cyan": COLORS["accent_cyan"],
        "success": COLORS["success"],
        "warning": COLORS["warning"],
        "error": COLORS["error"],
    }

    bg_color = color_map.get(color_scheme, COLORS["accent_blue"])

    return rx.button(
        text,
        background=bg_color,
        color="white",
        border="none",
        border_radius="8px",
        padding_x="20px",
        padding_y="10px",
        font_weight="500",
        font_size="14px",
        cursor="pointer",
        transition="all 0.2s",
        _hover={
            "opacity": "0.9",
            "transform": "translateY(-1px)",
        },
        **kwargs,
    )


def styled_select(**kwargs) -> rx.Component:
    """Styled select dropdown with dark theme."""
    default_style = {
        "background": COLORS["bg_tertiary"],
        "border": f"1px solid {COLORS['border']}",
        "border_radius": "8px",
        "color": COLORS["text_primary"],
    }
    return rx.select(**{**default_style, **kwargs})


def environment_field_row(info: dict) -> rx.Component:
    key = info.get("key", "")
    label = info.get("label", key)
    tooltip_text = info.get("tooltip", "")
    placeholder = info.get("placeholder", "")

    badge = Badge.create(
        label,
        size="1",
        color_scheme="cyan",
        high_contrast=True,
        radius="medium",
    )

    tooltip = rx.tooltip(
        badge,
        content=tooltip_text,
        delay_duration=200,
    )

    return rx.box(
        rx.hstack(
            tooltip,
            rx.spacer(),
        ),
        styled_input(
            value=PlaygroundState.environment_editor.get(key, ""),
            on_change=lambda value, key=key: PlaygroundState.edit_environment_value(key, value),
            placeholder=placeholder,
        ),
        rx.flex(
            styled_button(
                "Reset",
                on_click=PlaygroundState.reset_environment_value(key),
                color_scheme="error",
            ),
            styled_button(
                "Update",
                on_click=PlaygroundState.apply_environment_value(key),
                color_scheme="cyan",
            ),
            gap="12px",
            align="center",
            justify="end",
            width="100%",
        ),
        display="flex",
        flex_direction="column",
        gap="12px",
        padding="16px",
        background=COLORS["bg_tertiary"],
        border=f"1px solid {COLORS['border_subtle']}",
        border_radius="8px",
    )


EDITOR_HEIGHT = "320px"
STATE_HEIGHT = "360px"
LOAD_VIEW_HEIGHT = "378px"


def expert_section() -> rx.Component:
    return card(
        rx.accordion.root(
            rx.accordion.item(
                header=rx.accordion.trigger(
                    rx.hstack(
                        rx.heading(
                            "Execution Environment Variables",
                            size="4",
                            color=COLORS["text_primary"],
                            font_weight="600",
                        ),
                        rx.spacer(),
                        rx.accordion.icon(color=COLORS["accent_cyan"]),
                    ),
                    padding_y="8px",
                    padding_x="12px",
                ),
                content=rx.accordion.content(
                    rx.box(
                        rx.vstack(
                            rx.text(
                                "Configure deterministic runtime context. Leave a field blank to fall back to live defaults.",
                                color=COLORS["text_primary"],
                                size="2",
                                line_height="1.6",
                            ),
                            rx.text(
                                "Note: ctx.caller is managed by the runtime during contract-to-contract calls and cannot be overridden here.",
                                color=COLORS["text_secondary"],
                                font_style="italic",
                                size="1",
                                line_height="1.6",
                            ),
                            rx.flex(
                                *[environment_field_row(field) for field in ENVIRONMENT_FIELDS],
                                wrap="wrap",
                                spacing="3",
                                width="100%",
                                align="stretch",
                            ),
                            gap="16px",
                            width="100%",
                        ),
                        background=COLORS["bg_secondary"],
                        border=f"1px solid {COLORS['border']}",
                        border_radius="8px",
                        padding="16px",
                    ),
                    padding_top="12px",
                ),
                value="expert",
            ),
            type="single",
            collapsible=True,
            width="100%",
            default_value="expert",
            class_name="playground-env-accordion",
        ),
    )


def editor_section(card_kwargs: Dict[str, Any] | None = None) -> rx.Component:
    card_kwargs = card_kwargs or {}
    is_fullscreen = card_kwargs.get("flex") is not None
    editor_height = "100%" if is_fullscreen else EDITOR_HEIGHT

    editor_container_kwargs: Dict[str, Any] = {
        "width": "100%",
        "display": "flex",
        "min_height": EDITOR_HEIGHT,
        "max_height": EDITOR_HEIGHT,
        "height": EDITOR_HEIGHT,
        "overflow": "hidden",
    }
    if is_fullscreen:
        editor_container_kwargs.update(
            {
                "flex": "1 1 auto",
                "min_height": "0",
                "max_height": None,
                "height": "100%",
            }
        )

    return card(
        section_header(
            "Write Contract",
            "Write a Python smart contract, pick a unique name, and deploy it into the local sandbox.",
            panel_id="write",
            icon="file-pen",
        ),
        styled_input(
            placeholder="Contract name",
            value=PlaygroundState.contract_name,
            on_change=PlaygroundState.update_contract_name,
        ),
        rx.box(
            MonacoEditor.create(
                default_value=PlaygroundState.code_editor,
                language="python",
                theme="vs-dark",
                height=editor_height,
                options={
                    "automaticLayout": True,
                    "tabSize": 4,
                    "insertSpaces": True,
                    "scrollBeyondLastLine": False,
                    "wordWrap": "on",
                    "minimap": {"enabled": False},
                    "lineNumbers": "on",
                    "renderWhitespace": "selection",
                    "padding": {"top": 12, "bottom": 12},
                },
                on_change=PlaygroundState.update_code,
                key=PlaygroundState.code_editor_revision,
                class_name="playground-monaco",
            ),
            **editor_container_kwargs,
        ),
        rx.hstack(
            styled_button(
                "Save Draft",
                on_click=PlaygroundState.save_code_draft,
                color_scheme="blue",
            ),
            rx.spacer(),
            styled_button(
                "Deploy Contract",
                on_click=PlaygroundState.deploy_contract,
                color_scheme="purple",
            ),
            styled_button(
                rx.cond(
                    PlaygroundState.linting,
                    "Linting...",
                    "Run Linter",
                ),
                on_click=PlaygroundState.lint_contract,
                color_scheme="cyan",
                disabled=PlaygroundState.linting,
            ),
            width="100%",
            spacing="3",
        ),
        rx.cond(
            PlaygroundState.lint_results != [],
            rx.box(
                rx.foreach(
                    PlaygroundState.lint_results,
                    lambda message: rx.text(
                        message,
                        color=COLORS["warning"],
                        size="2",
                    ),
                ),
                padding="12px",
                border=f"1px solid {COLORS['border']}",
                border_radius="8px",
                background=COLORS["bg_tertiary"],
                width="100%",
                gap="8px",
            ),
            rx.fragment(),
        ),
        **card_kwargs,
    )


def load_section(card_kwargs: Dict[str, Any] | None = None) -> rx.Component:
    card_kwargs = card_kwargs or {}
    is_fullscreen = card_kwargs.get("flex") is not None
    panel_height = "100%" if is_fullscreen else LOAD_VIEW_HEIGHT
    viewer_props: Dict[str, Any] = {
        "display": "flex",
        "flex_direction": "column",
        "gap": "12px",
        "width": "100%",
    }
    if is_fullscreen:
        viewer_props.update(
            {
                "flex": "1 1 auto",
                "min_height": "0",
            }
        )
    else:
        viewer_props.update(
            {
                "height": panel_height,
                "min_height": panel_height,
                "max_height": panel_height,
            }
        )

    code_box_props: Dict[str, Any] = {
        "flex": "1 1 auto",
        "width": "100%",
        "overflow": "auto",
        "min_height": "0",
        "background": COLORS["bg_tertiary"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "8px",
        "padding": "12px",
    }
    if not is_fullscreen:
        code_box_props["height"] = "100%"

    return card(
        section_header(
            "Load Contract",
            "Inspect deployed contract source code.",
            panel_id="load",
            icon="folder-open",
        ),
        rx.hstack(
            rx.box(
                styled_select(
                    items=PlaygroundState.deployed_contracts,
                    value=PlaygroundState.load_selected_contract,
                    placeholder="Select a contract",
                    on_change=PlaygroundState.change_loaded_contract,
                    disabled=PlaygroundState.deployed_contracts == [],
                    width="100%",
                ),
                flex="1",
            ),
            styled_button(
                "Remove Contract",
                on_click=PlaygroundState.remove_selected_contract,
                color_scheme="error",
                disabled=PlaygroundState.load_selected_contract == "",
            ),
            spacing="3",
            width="100%",
            align_items="center",
        ),
        rx.cond(
            PlaygroundState.load_selected_contract == "",
            rx.box(
                rx.text(
                    "Select a deployed contract to review its source and exports.",
                    color=COLORS["text_muted"],
                    size="2",
                ),
                padding="12px",
                border=f"1px dashed {COLORS['border']}",
                border_radius="8px",
            ),
            rx.box(
                rx.hstack(
                    rx.text(
                        rx.cond(
                            PlaygroundState.load_view_decompiled,
                            "Decompiled",
                            "Raw",
                        ),
                        color=COLORS["text_secondary"],
                        size="2",
                    ),
                    rx.spacer(),
                    rx.switch(
                        checked=PlaygroundState.load_view_decompiled,
                        on_change=lambda value: PlaygroundState.toggle_load_view(),
                        color_scheme="cyan",
                    ),
                    spacing="3",
                    align_items="center",
                    width="100%",
                ),
                rx.box(
                    rx.cond(
                        PlaygroundState.load_view_decompiled,
                        code_viewer(
                            PlaygroundState.loaded_contract_decompiled,
                            "python",
                            "# Decompiled source unavailable.",
                            font_size="12px",
                        ),
                        code_viewer(
                            PlaygroundState.loaded_contract_code,
                            "python",
                            "# Source unavailable.",
                            font_size="12px",
                        ),
                    ),
                    **code_box_props,
                ),
                **viewer_props,
            ),
        ),
        **card_kwargs,
    )


def execution_section(card_kwargs: Dict[str, Any] | None = None) -> rx.Component:
    card_kwargs = card_kwargs or {}
    is_fullscreen = card_kwargs.get("flex") is not None

    textarea_kwargs: Dict[str, Any] = {
        "placeholder": 'Kwargs as JSON, e.g. {"to": "alice", "amount": 25}',
        "value": PlaygroundState.kwargs_input,
        "on_change": PlaygroundState.update_kwargs,
        "font_family": "'Fira Code', 'Monaco', 'Courier New', monospace",
        "spell_check": False,
        "min_height": "120px",
        "height": "100%",
    }
    textarea_container_props: Dict[str, Any] = {
        "width": "100%",
        "flex": "1 1 auto",
        "min_height": "120px",
        "overflow": "hidden",
        "display": "flex",
        "flex_direction": "column",
    }

    result_panel_props: Dict[str, Any] = {
        "display": rx.cond(PlaygroundState.run_result == "", "none", "flex"),
        "flex_direction": "column",
        "gap": "12px",
        "width": "100%",
        "flex": "0 0 auto",
        "max_height": "50vh" if is_fullscreen else "360px",
    }
    result_box_props: Dict[str, Any] = {
        "width": "100%",
        "overflow": "auto",
        "background": COLORS["bg_tertiary"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "8px",
        "padding": "12px",
        "max_height": "50vh" if is_fullscreen else "300px",
    }

    return card(
        section_header(
            "Execute Contract",
            "Pick a deployed contract and exported function to run.",
            panel_id="execute",
            icon="play",
        ),
        styled_select(
            items=PlaygroundState.deployed_contracts,
            value=PlaygroundState.selected_contract,
            placeholder="Select a contract",
            on_change=PlaygroundState.change_selected_contract,
        ),
        styled_select(
            items=PlaygroundState.available_functions,
            value=PlaygroundState.function_name,
            placeholder="Select a function",
            on_change=PlaygroundState.change_selected_function,
        ),
        rx.box(
            styled_text_area(**textarea_kwargs),
            **textarea_container_props,
        ),
        styled_button(
            "Run Function",
            on_click=PlaygroundState.run_contract,
            color_scheme="success",
        ),
        rx.box(
            height="1px",
            width="100%",
            background=COLORS["border"],
        ),
        rx.box(
            rx.hstack(
                rx.icon(tag="terminal", size=18, color=COLORS["accent_cyan"]),
                rx.heading(
                    "Result",
                    size="3",
                    color=COLORS["text_primary"],
                    font_weight="600",
                ),
                align_items="center",
                gap="8px",
            ),
            rx.box(
                code_viewer(
                    PlaygroundState.run_result,
                    "json",
                    "Awaiting execution...",
                    font_size="12px",
                ),
                **result_box_props,
            ),
            **result_panel_props,
        ),
        **card_kwargs,
    )


def state_section(card_kwargs: Dict[str, Any] | None = None) -> rx.Component:
    card_kwargs = card_kwargs or {}
    is_fullscreen = card_kwargs.get("flex") is not None
    panel_height = "100%" if is_fullscreen else STATE_HEIGHT

    header_actions = rx.cond(
        PlaygroundState.state_is_editing,
        rx.hstack(
            styled_button(
                "Save Changes",
                color_scheme="success",
                on_click=PlaygroundState.toggle_state_editor,
            ),
            styled_button(
                "Cancel",
                color_scheme="error",
                on_click=PlaygroundState.cancel_state_editing,
            ),
            spacing="3",
            align="center",
            justify="end",
        ),
        styled_button(
            "Edit State",
            color_scheme="cyan",
            on_click=PlaygroundState.toggle_state_editor,
        ),
    )

    outer_panel_props: Dict[str, Any] = {
        "width": "100%",
        "display": "flex",
        "flex_direction": "column",
        "gap": "12px",
        "flex": "1 1 auto",
    }
    if is_fullscreen:
        outer_panel_props.update(
            {
                "height": "100%",
                "min_height": "0",
            }
        )
    else:
        outer_panel_props.update(
            {
                "height": panel_height,
                "min_height": panel_height,
                "max_height": panel_height,
            }
        )

    inner_box_props: Dict[str, Any] = {
        "flex": "1 1 auto",
        "width": "100%",
        "overflow": "auto",
        "min_height": "0",
        "background": COLORS["bg_tertiary"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "8px",
        "padding": "12px",
    }
    if not is_fullscreen:
        inner_box_props["height"] = "100%"

    return card(
        section_header(
            "Contract State",
            "Live snapshot of every key stored in the driver. Refreshes after deployments and executions.",
            panel_id="state",
            icon="database",
        ),
        rx.hstack(
            rx.checkbox(
                checked=PlaygroundState.show_internal_state,
                on_change=PlaygroundState.set_show_internal_state,
                color_scheme="cyan",
            ),
            rx.text(
                "Show protected state keys",
                color=COLORS["text_primary"],
                size="2",
                cursor="pointer",
                on_click=PlaygroundState.toggle_show_internal_state,
            ),
            rx.spacer(),
            header_actions,
            align_items="center",
            spacing="3",
            width="100%",
        ),
        rx.cond(
            PlaygroundState.state_is_editing,
            rx.box(
                rx.box(
                    styled_text_area(
                        value=PlaygroundState.state_editor,
                        on_change=PlaygroundState.update_state_editor,
                        font_family="'Fira Code', 'Monaco', 'Courier New', monospace",
                        width="100%",
                        overflow_y="auto",
                        spell_check=False,
                        height="100%",
                    ),
                    **inner_box_props,
                ),
                **outer_panel_props,
            ),
            rx.box(
                rx.box(
                    code_viewer(
                        PlaygroundState.state_dump,
                        "json",
                        "State is empty.",
                        font_size="12px",
                    ),
                    **inner_box_props,
                ),
                **outer_panel_props,
            ),
        ),
        rx.hstack(
            rx.alert_dialog.root(
                rx.alert_dialog.trigger(
                    styled_button(
                        "Clear All State",
                        color_scheme="error",
                    ),
                ),
                rx.alert_dialog.content(
                    rx.vstack(
                        rx.alert_dialog.title(
                            "Clear all contracts and runtime state?",
                        ),
                        rx.alert_dialog.description(
                            "This wipes every deployed contract (except the system submission contract) and resets the driver. This cannot be undone.",
                        ),
                        rx.hstack(
                            rx.alert_dialog.cancel(
                                styled_button(
                                    "Cancel",
                                    color_scheme="blue",
                                ),
                            ),
                            rx.alert_dialog.action(
                                styled_button(
                                    "Confirm Clear",
                                    color_scheme="error",
                                    on_click=PlaygroundState.confirm_clear_state,
                                ),
                            ),
                            spacing="3",
                            justify="end",
                            width="100%",
                        ),
                        spacing="4",
                        align_items="stretch",
                    ),
                    max_width="420px",
                    background=COLORS["bg_secondary"],
                    border=f"1px solid {COLORS['border']}",
                    border_radius="12px",
                    padding="24px",
                ),
            ),
            rx.spacer(),
            styled_button(
                "Export State",
                on_click=PlaygroundState.export_state,
                color_scheme="cyan",
            ),
            rx.upload(
                styled_button(
                    "Import State",
                    color_scheme="purple",
                ),
                accept={"application/json": [".json"]},
                multiple=False,
                max_files=1,
                on_drop=PlaygroundState.import_state,
                no_drag=True,
                style={
                    "display": "inline-flex",
                    "border": "none",
                    "padding": "0",
                    "background": "transparent",
                },
                class_name="playground-upload",
            ),
            spacing="3",
            align_items="center",
            width="100%",
        ),
        **card_kwargs,
    )


def expanded_panel_content() -> rx.Component:
    fullscreen_card_props = {
        "height": "100%",
        "min_height": "0",
        "flex": "1 1 auto",
        "display": "flex",
        "flex_direction": "column",
        "class_name": "fullscreen-card",
    }

    return rx.cond(
        PlaygroundState.expanded_panel == "write",
        editor_section(card_kwargs=fullscreen_card_props),
        rx.cond(
            PlaygroundState.expanded_panel == "load",
            load_section(card_kwargs=fullscreen_card_props),
            rx.cond(
                PlaygroundState.expanded_panel == "execute",
                execution_section(card_kwargs=fullscreen_card_props),
                state_section(card_kwargs=fullscreen_card_props),
            ),
        ),
    )


def fullscreen_overlay() -> rx.Component:
    return rx.cond(
        PlaygroundState.expanded_panel != "",
        rx.fragment(
            rx.window_event_listener(
                on_key_down=PlaygroundState.handle_fullscreen_keydown
            ),
            rx.box(
                expanded_panel_content(),
                position="fixed",
                inset="0",
                padding=["16px", "24px", "32px"],
                background=COLORS["bg_primary"],
                min_height="100vh",
                height="100vh",
                display="flex",
                flex_direction="column",
                align_items="stretch",
                overflow_y="auto",
                z_index="1000",
            ),
        ),
        rx.fragment(),
    )


def header() -> rx.Component:
    """Modern header with gradient accent."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.box(
                    rx.heading(
                        "Xian",
                        size="8",
                        color=COLORS["text_primary"],
                        font_weight="700",
                        letter_spacing="-0.02em",
                    ),
                    rx.heading(
                        "Contracting Playground",
                        size="8",
                        background=f"linear-gradient(135deg, {COLORS['accent_purple']} 0%, {COLORS['accent_cyan']} 100%)",
                        background_clip="text",
                        color="transparent",
                        font_weight="700",
                        letter_spacing="-0.02em",
                    ),
                    gap="8px",
                    display="flex",
                    flex_direction="row",
                    align_items="baseline",
                    flex_wrap="wrap",
                ),
                align_items="baseline",
        ),
        rx.text(
            "Deploy Python smart contracts, execute exported functions, and inspect resulting state without leaving the browser.",
            color=COLORS["text_secondary"],
            size="3",
            line_height="1.6",
        ),
            gap="12px",
            align_items="start",
            width="100%",
        ),
        padding_y="32px",
        width="100%",
    )


def index() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.box(
                header(),
                width="100%",
                max_width="1400px",
                margin_x="auto",
                padding_x=["16px", "24px", "32px"],
            ),
            rx.box(
                rx.vstack(
                    session_panel(),
                    # Main content grid - Editor and Execution side by side
                    rx.box(
                        rx.grid(
                            editor_section(),
                            load_section(),
                            execution_section(),
                            state_section(),
                            columns="2",
                            spacing="5",
                            width="100%",
                        ),
                        width="100%",
                        display=["none", "none", "block"],  # Hide on mobile
                    ),
                    # Mobile stack layout
                    rx.box(
                        rx.vstack(
                            editor_section(),
                            load_section(),
                            execution_section(),
                            state_section(),
                            spacing="5",
                            width="100%",
                        ),
                        width="100%",
                        display=["block", "block", "none"],  # Show on mobile
                    ),
                    # Full width expert section
                    expert_section(),
                    spacing="5",
                    width="100%",
                ),
                width="100%",
                max_width="1400px",
                margin_x="auto",
                padding_x=["16px", "24px", "32px"],
                padding_bottom="64px",
            ),
            spacing="0",
            width="100%",
        ),
        fullscreen_overlay(),
        background=COLORS["bg_primary"],
        min_height="100vh",
        width="100%",
    )


app = rx.App(
    theme=rx.theme(
        appearance="dark",
        accent_color="cyan",
        gray_color="slate",
        radius="large",
        scaling="100%",
    ),
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
        "/editor.css",
    ],
)

app.add_page(
    index,
    title="Xian Contracting Playground",
    on_load=PlaygroundState.on_load,
)

app._api.add_middleware(SessionCookieMiddleware)


def _frontend_redirect_target(request: Request) -> str:
    next_param = request.query_params.get("next")
    if next_param:
        return unquote(next_param)
    referer = request.headers.get("referer")
    if referer:
        return referer
    deploy = get_config().deploy_url
    if deploy:
        return deploy
    return "/"


@app._api.route("/sessions/new", methods=["GET"])
async def create_session_route(request: Request):
    metadata = session_runtime.create_session()
    response = RedirectResponse(_frontend_redirect_target(request))
    issue_session_cookie(response, metadata.session_id)
    return response


@app._api.route("/sessions/{session_id}", methods=["GET"])
async def resume_session_route(request: Request):
    raw = request.path_params.get("session_id", "").lower()
    if not SessionRepository.is_valid_session_id(raw):
        return RedirectResponse("/sessions/new")
    if not session_runtime.session_exists(raw):
        return RedirectResponse("/sessions/new")
    metadata = session_runtime.ensure_exists(raw)
    response = RedirectResponse(_frontend_redirect_target(request))
    issue_session_cookie(response, metadata.session_id)
    return response
