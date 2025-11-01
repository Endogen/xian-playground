from __future__ import annotations

import reflex as rx

from .services import ENVIRONMENT_FIELDS
from .state import PlaygroundState


def environment_field_row(info: dict) -> rx.Component:
    key = info.get("key", "")
    label = info.get("label", key)
    tooltip_text = info.get("tooltip", "")
    placeholder = info.get("placeholder", "")

    tooltip = rx.tooltip(
        rx.text(label, font_weight="bold"),
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
                variant="soft",
                color_scheme="gray",
            ),
        ),
        rx.input(
            value=PlaygroundState.environment_editor.get(key, ""),
            on_change=lambda value, key=key: PlaygroundState.edit_environment_value(key, value),
            placeholder=placeholder,
        ),
        rx.hstack(
            rx.spacer(),
            rx.button(
                "Update",
                on_click=PlaygroundState.apply_environment_value(key),
                color_scheme="blue",
            ),
        ),
        display="flex",
        flex_direction="column",
        gap="2",
        padding="3",
        border="1px solid var(--gray-5)",
        border_radius="6px",
    )


EDITOR_HEIGHT = "320px"
STATE_HEIGHT = "360px"


def expert_section() -> rx.Component:
    return rx.accordion.root(
        rx.accordion.item(
            header=rx.accordion.trigger(
                rx.hstack(
                    rx.text("Expert"),
                    rx.spacer(),
                    rx.accordion.icon(),
                ),
                padding_y="2",
            ),
            content=rx.accordion.content(
                rx.vstack(
                    rx.text(
                        "Advanced controls for signer identity and state visibility.",
                        color="gray9",
                    ),
                    rx.hstack(
                        rx.checkbox(
                            checked=PlaygroundState.show_internal_state,
                            on_change=PlaygroundState.set_show_internal_state,
                        ),
                        rx.text("Show state keys starting with '__'"),
                        gap="2",
                    ),
                    rx.divider(),
                    rx.heading("Execution Environment", size="3"),
                    rx.text(
                        "Configure deterministic runtime context. Leave a field blank to fall back to live defaults.",
                        color="gray9",
                    ),
                    rx.vstack(
                        *[environment_field_row(field) for field in ENVIRONMENT_FIELDS],
                        gap="3",
                        width="100%",
                    ),
                    rx.cond(
                        PlaygroundState.expert_message != "",
                        rx.text(
                            PlaygroundState.expert_message,
                            color=rx.cond(
                                PlaygroundState.expert_is_error,
                                "red",
                                "green",
                            ),
                        ),
                        rx.box(),
                    ),
                    gap="4",
                    width="100%",
                ),
                padding_y="4",
            ),
            value="expert",
        ),
        type="single",
        collapsible=True,
        width="100%",
    )


def editor_section() -> rx.Component:
    return rx.box(
        rx.heading("Smart Contract", size="4"),
        rx.text(
            "Write or paste a Python smart contract, pick a unique name, and deploy it into the local sandbox.",
            color="gray9",
        ),
        rx.input(
            placeholder="Contract name",
            value=PlaygroundState.contract_name,
            on_change=PlaygroundState.update_contract_name,
        ),
        rx.text_area(
            value=PlaygroundState.code_editor,
            on_change=PlaygroundState.update_code,
            min_height=EDITOR_HEIGHT,
            font_family="monospace",
            spell_check=False,
        ),
        rx.hstack(
            rx.spacer(),
            rx.button(
                "Deploy",
                on_click=PlaygroundState.deploy_contract,
                color_scheme="orange",
            ),
        ),
        rx.cond(
            PlaygroundState.deploy_message != "",
            rx.text(
                PlaygroundState.deploy_message,
                color=rx.cond(PlaygroundState.deploy_is_error, "red", "green"),
            ),
            rx.box(),
        ),
        display="flex",
        flex_direction="column",
        gap="4",
        width="100%",
    )


def execution_section() -> rx.Component:
    return rx.box(
        rx.heading("Execute Contract", size="4"),
        rx.text("Pick a deployed contract and exported function to run."),
        rx.select(
            items=PlaygroundState.deployed_contracts,
            value=PlaygroundState.selected_contract,
            placeholder="Select a contract",
            on_change=PlaygroundState.change_selected_contract,
        ),
        rx.select(
            items=PlaygroundState.available_functions,
            value=PlaygroundState.function_name,
            placeholder="Select a function",
            on_change=PlaygroundState.change_selected_function,
        ),
        rx.text_area(
            placeholder='Kwargs as JSON, e.g. {"to": "alice", "amount": 25}',
            value=PlaygroundState.kwargs_input,
            on_change=PlaygroundState.update_kwargs,
            font_family="monospace",
            min_height="120px",
            spell_check=False,
        ),
        rx.button(
            "Run",
            on_click=PlaygroundState.run_contract,
            color_scheme="grass",
        ),
        rx.heading("Result", size="3"),
        rx.code_block(
            rx.cond(
                PlaygroundState.run_result == "",
                "Awaiting execution...",
                PlaygroundState.run_result,
            ),
            language="json",
            wrap_lines=True,
            width="100%",
        ),
        display="flex",
        flex_direction="column",
        gap="4",
        width="100%",
    )


def state_section() -> rx.Component:
    return rx.box(
        rx.heading("Contract State", size="4"),
        rx.text(
            "Live snapshot of every key stored in the driver. Refreshes after deployments and executions."
        ),
        rx.code_block(
            PlaygroundState.state_dump,
            language="json",
            wrap_lines=True,
            width="100%",
            min_height=STATE_HEIGHT,
            max_height="520px",
            overflow_y="auto",
        ),
        display="flex",
        flex_direction="column",
        gap="4",
        width="100%",
    )


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Xian Contracting Playground", size="6"),
            rx.text(
                "Deploy Python smart contracts, execute exported functions, and inspect resulting state without leaving the browser.",
                color="gray9",
            ),
            rx.grid(
                editor_section(),
                execution_section(),
                state_section(),
                template_columns="repeat(auto-fit, minmax(320px, 1fr))",
                gap="5",
                width="100%",
            ),
            expert_section(),
            spacing="5",
            width="100%",
        ),
        padding_y="2em",
        max_width="1200px",
    )


app = rx.App()
app.add_page(
    index,
    title="Xian Contracting Playground",
    on_load=PlaygroundState.on_load,
)
