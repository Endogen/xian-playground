"""Monaco editor integration for Reflex."""

from __future__ import annotations

from typing import Any

from reflex.components.component import NoSSRComponent
from reflex.event import EventHandler, passthrough_event_spec
from reflex.vars import Var


class MonacoEditor(NoSSRComponent):
    """Wrapper around @monaco-editor/react."""

    library = "@monaco-editor/react@4.6.0"
    lib_dependencies = ["monaco-editor@0.45.0"]
    tag = "Editor"
    is_default = True

    value: Var[str]
    language: Var[str] = Var.create("python")
    theme: Var[str] = Var.create("vs-dark")
    height: Var[str] = Var.create("320px")
    options: Var[dict[str, Any]] = Var.create({})

    on_change: EventHandler[passthrough_event_spec(str)]
