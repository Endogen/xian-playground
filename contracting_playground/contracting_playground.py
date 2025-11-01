from __future__ import annotations

import reflex as rx

from .components import MonacoEditor
from .services import ENVIRONMENT_FIELDS
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
    }
    return rx.box(*children, **{**default_style, **kwargs})


def section_header(title: str, description: str = "") -> rx.Component:
    """Section header with title and optional description."""
    return rx.vstack(
        rx.heading(
            title,
            size="5",
            color=COLORS["text_primary"],
            font_weight="600",
        ),
        rx.cond(
            description != "",
            rx.text(
                description,
                color=COLORS["text_secondary"],
                size="2",
                line_height="1.6",
            ),
        ),
        gap="8px",
        align_items="start",
        width="100%",
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

    tooltip = rx.tooltip(
        rx.text(
            label,
            font_weight="500",
            color=COLORS["text_primary"],
            size="2",
        ),
        content=tooltip_text,
        delay_duration=200,
    )

    return rx.box(
        rx.hstack(
            tooltip,
            rx.spacer(),
            rx.button(
                "Reset",
                on_click=PlaygroundState.reset_environment_value(key),
                background=COLORS["bg_tertiary"],
                color=COLORS["text_secondary"],
                border=f"1px solid {COLORS['border']}",
                border_radius="6px",
                padding_x="12px",
                padding_y="6px",
                font_size="13px",
                cursor="pointer",
                _hover={"background": COLORS["border"]},
            ),
            width="100%",
            gap="12px",
        ),
        styled_input(
            value=PlaygroundState.environment_editor.get(key, ""),
            on_change=lambda value, key=key: PlaygroundState.edit_environment_value(key, value),
            placeholder=placeholder,
        ),
        rx.hstack(
            rx.spacer(),
            styled_button(
                "Update",
                on_click=PlaygroundState.apply_environment_value(key),
                color_scheme="cyan",
            ),
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


def expert_section() -> rx.Component:
    return card(
        rx.accordion.root(
            rx.accordion.item(
                header=rx.accordion.trigger(
                    rx.hstack(
                        rx.heading(
                            "Expert Settings",
                            size="4",
                            color=COLORS["text_primary"],
                            font_weight="600",
                        ),
                        rx.spacer(),
                        rx.accordion.icon(color=COLORS["accent_cyan"]),
                    ),
                    padding_y="4px",
                ),
                content=rx.accordion.content(
                    rx.vstack(
                        rx.text(
                            "Advanced controls for signer identity and state visibility.",
                            color=COLORS["text_secondary"],
                            size="2",
                            line_height="1.6",
                        ),
                        rx.hstack(
                            rx.checkbox(
                                checked=PlaygroundState.show_internal_state,
                                on_change=PlaygroundState.set_show_internal_state,
                                color_scheme="cyan",
                            ),
                            rx.text(
                                "Show state keys starting with '__'",
                                color=COLORS["text_primary"],
                                size="2",
                            ),
                            gap="12px",
                            align_items="center",
                        ),
                        rx.box(
                            height="1px",
                            width="100%",
                            background=COLORS["border"],
                        ),
                        rx.heading(
                            "Execution Environment",
                            size="3",
                            color=COLORS["text_primary"],
                            font_weight="600",
                        ),
                        rx.text(
                            "Configure deterministic runtime context. Leave a field blank to fall back to live defaults.",
                            color=COLORS["text_secondary"],
                            size="2",
                            line_height="1.6",
                        ),
                        rx.text(
                            "Note: ctx.caller is managed by the runtime during contract-to-contract calls and cannot be overridden here.",
                            color=COLORS["text_muted"],
                            font_style="italic",
                            size="1",
                            line_height="1.6",
                        ),
                        rx.vstack(
                            *[environment_field_row(field) for field in ENVIRONMENT_FIELDS],
                            gap="12px",
                            width="100%",
                        ),
                        gap="16px",
                        width="100%",
                    ),
                    padding_y="16px",
                ),
                value="expert",
            ),
            type="single",
            collapsible=True,
            width="100%",
            background="transparent",
        ),
    )


def editor_section() -> rx.Component:
    return card(
        section_header(
            "Smart Contract",
            "Write or paste a Python smart contract, pick a unique name, and deploy it into the local sandbox.",
        ),
        styled_input(
            placeholder="Contract name",
            value=PlaygroundState.contract_name,
            on_change=PlaygroundState.update_contract_name,
        ),
        MonacoEditor.create(
            value=PlaygroundState.code_editor,
            language="python",
            theme="vs-dark",
            height=EDITOR_HEIGHT,
            options={
                "automaticLayout": True,
                "tabSize": 4,
                "insertSpaces": True,
                "scrollBeyondLastLine": False,
                "wordWrap": "on",
                "minimap": {"enabled": False},
                "lineNumbers": "on",
                "renderWhitespace": "selection",
            },
            on_change=PlaygroundState.update_code,
        ),
        rx.hstack(
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
    )


def execution_section() -> rx.Component:
    return card(
        section_header(
            "Execute Contract",
            "Pick a deployed contract and exported function to run.",
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
        styled_text_area(
            placeholder='Kwargs as JSON, e.g. {"to": "alice", "amount": 25}',
            value=PlaygroundState.kwargs_input,
            on_change=PlaygroundState.update_kwargs,
            font_family="'Fira Code', 'Monaco', 'Courier New', monospace",
            min_height="120px",
            spell_check=False,
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
        rx.heading(
            "Result",
            size="3",
            color=COLORS["text_primary"],
            font_weight="600",
        ),
        rx.box(
            rx.code_block(
                rx.cond(
                    PlaygroundState.run_result == "",
                    "Awaiting execution...",
                    PlaygroundState.run_result,
                ),
                language="json",
                wrap_lines=True,
                width="100%",
                background=COLORS["bg_tertiary"],
            ),
            background=COLORS["bg_tertiary"],
            border=f"1px solid {COLORS['border']}",
            border_radius="8px",
            padding="12px",
            overflow="auto",
        ),
    )


def state_section() -> rx.Component:
    return card(
        rx.hstack(
            section_header(
                "Contract State",
                "Live snapshot of every key stored in the driver. Refreshes after deployments and executions.",
            ),
            rx.spacer(),
            rx.cond(
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
            ),
            align_items="center",
            spacing="4",
            width="100%",
        ),
        rx.cond(
            PlaygroundState.state_is_editing,
            rx.box(
                styled_text_area(
                    value=PlaygroundState.state_editor,
                    on_change=PlaygroundState.update_state_editor,
                    font_family="'Fira Code', 'Monaco', 'Courier New', monospace",
                    min_height=STATE_HEIGHT,
                    max_height="520px",
                    width="100%",
                    overflow_y="auto",
                    spell_check=False,
                ),
            ),
            rx.box(
                rx.code_block(
                    PlaygroundState.state_dump,
                    language="json",
                    wrap_lines=True,
                    width="100%",
                    min_height=STATE_HEIGHT,
                    max_height="520px",
                    overflow_y="auto",
                    background=COLORS["bg_tertiary"],
                ),
                background=COLORS["bg_tertiary"],
                border=f"1px solid {COLORS['border']}",
                border_radius="8px",
                padding="12px",
                overflow="auto",
            ),
        ),
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
                max_width="800px",
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
                    # Main content grid - Editor and Execution side by side
                    rx.box(
                        rx.grid(
                            editor_section(),
                            execution_section(),
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
                            execution_section(),
                            spacing="5",
                            width="100%",
                        ),
                        width="100%",
                        display=["block", "block", "none"],  # Show on mobile
                    ),
                    # Full width state section
                    state_section(),
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
    ],
)

app.add_page(
    index,
    title="Xian Contracting Playground",
    on_load=PlaygroundState.on_load,
)
