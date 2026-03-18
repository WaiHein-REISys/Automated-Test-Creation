"""Config Editor — form-based config creation and editing."""

from __future__ import annotations

import json
from pathlib import Path

from nicegui import ui

from atc.infra.config import RunConfig
from atc.ui.state import app_state

# Provider choices
PROVIDER_TYPES = ["prompt_only", "claude", "azure_openai", "ollama", "cli_agent"]

# Default models per provider
DEFAULT_MODELS = {
    "claude": "claude-sonnet-4-20250514",
    "azure_openai": "",
    "ollama": "llama3",
    "cli_agent": "",
    "prompt_only": "",
}


def render() -> None:
    """Render the config editor page."""
    ui.label("Run Configuration").classes("text-3xl font-bold")

    # Config file management
    with ui.row().classes("w-full items-center gap-2"):
        config_path_input = ui.input(
            "Config file path",
            value=app_state.config_path or "run.json",
        ).classes("flex-1")

        ui.button("Load", icon="upload_file", on_click=lambda: _load_config(config_path_input.value))
        ui.button("Save", icon="save", on_click=lambda: _save_config(config_path_input.value)).props(
            "color=positive"
        )
        ui.button("New", icon="add", on_click=_new_config)

    ui.separator()

    # Two-column layout: form | JSON preview
    with ui.row().classes("w-full gap-4"):
        # Left: Form
        with ui.column().classes("flex-1 gap-3"):
            ui.label("Configuration").classes("text-xl font-semibold")

            # Core fields
            with ui.card().classes("w-full"):
                ui.label("Core Settings").classes("font-semibold text-blue-400")

                url_input = ui.input(
                    "ADO Work Item URL",
                    value=app_state.config_data.get("url", ""),
                    placeholder="https://dev.azure.com/org/project/_workitems/edit/12345",
                ).classes("w-full").on(
                    "change", lambda e: _update_field("url", e.sender.value)
                )

                product_input = ui.input(
                    "Product Name",
                    value=app_state.config_data.get("product_name", ""),
                    placeholder="e.g. EHB",
                ).classes("w-full").on(
                    "change", lambda e: _update_field("product_name", e.sender.value)
                )

                workspace_input = ui.input(
                    "Workspace Directory",
                    value=app_state.config_data.get("workspace_dir", "./workspace"),
                ).classes("w-full").on(
                    "change", lambda e: _update_field("workspace_dir", e.sender.value)
                )

            # Target repo
            with ui.card().classes("w-full"):
                ui.label("Target Repository").classes("font-semibold text-blue-400")

                repo_input = ui.input(
                    "Target Repo Path (optional)",
                    value=app_state.config_data.get("target_repo_path", "") or "",
                    placeholder="/path/to/automation/repo",
                ).classes("w-full").on(
                    "change",
                    lambda e: _update_field("target_repo_path", e.sender.value or None),
                )

                branch_input = ui.input(
                    "Branch Name (optional)",
                    value=app_state.config_data.get("branch_name", "") or "",
                    placeholder="dev/DME/feature/EHB",
                ).classes("w-full").on(
                    "change",
                    lambda e: _update_field("branch_name", e.sender.value or None),
                )

            # ADO API version
            with ui.card().classes("w-full"):
                ui.label("ADO API").classes("font-semibold text-blue-400")

                api_version_select = ui.select(
                    ["auto", "7.1", "7.0", "6.0"],
                    value=app_state.config_data.get("ado_api_version", "auto"),
                    label="API Version",
                ).classes("w-full").on(
                    "change", lambda e: _update_field("ado_api_version", e.sender.value)
                )

            # Provider config
            with ui.card().classes("w-full"):
                ui.label("AI Provider").classes("font-semibold text-blue-400")

                provider_data = app_state.config_data.get("provider", {})

                provider_type = ui.select(
                    PROVIDER_TYPES,
                    value=provider_data.get("type", "prompt_only"),
                    label="Provider Type",
                ).classes("w-full").on(
                    "change", lambda e: _update_provider_type(e.sender.value)
                )

                model_input = ui.input(
                    "Model",
                    value=provider_data.get("model", ""),
                    placeholder="Model name (e.g. claude-sonnet-4-20250514)",
                ).classes("w-full").on(
                    "change",
                    lambda e: _update_nested("provider", "model", e.sender.value),
                )

            # Options
            with ui.card().classes("w-full"):
                ui.label("Options").classes("font-semibold text-blue-400")

                options_data = app_state.config_data.get("options", {})

                ui.switch(
                    "Dry Run",
                    value=options_data.get("dry_run", False),
                    on_change=lambda e: _update_nested("options", "dry_run", e.value),
                )
                ui.switch(
                    "Download Attachments",
                    value=options_data.get("download_attachments", True),
                    on_change=lambda e: _update_nested(
                        "options", "download_attachments", e.value
                    ),
                )
                ui.switch(
                    "Include Images in Prompt",
                    value=options_data.get("include_images_in_prompt", True),
                    on_change=lambda e: _update_nested(
                        "options", "include_images_in_prompt", e.value
                    ),
                )

                gen_limit = ui.number(
                    "Generation Limit (0 = unlimited)",
                    value=options_data.get("generation_limit", 0),
                    min=0,
                ).classes("w-full").on(
                    "change",
                    lambda e: _update_nested(
                        "options", "generation_limit", int(e.sender.value or 0)
                    ),
                )

                per_feat_limit = ui.number(
                    "Per-Feature Limit (0 = unlimited)",
                    value=options_data.get("generation_limit_per_feature", 0),
                    min=0,
                ).classes("w-full").on(
                    "change",
                    lambda e: _update_nested(
                        "options", "generation_limit_per_feature", int(e.sender.value or 0)
                    ),
                )

                only_ids_input = ui.input(
                    "Generate Only IDs (comma-separated, empty = all)",
                    value=", ".join(
                        str(i) for i in options_data.get("generation_only_ids", [])
                    ),
                ).classes("w-full").on(
                    "change",
                    lambda e: _update_nested(
                        "options",
                        "generation_only_ids",
                        _parse_id_list(e.sender.value),
                    ),
                )

        # Right: JSON preview
        with ui.column().classes("flex-1 gap-3"):
            ui.label("JSON Preview").classes("text-xl font-semibold")
            with ui.card().classes("w-full"):
                json_preview = ui.code(
                    _format_json(),
                    language="json",
                ).classes("w-full")

            # Validate button
            with ui.row().classes("gap-2"):
                ui.button(
                    "Validate",
                    icon="check_circle",
                    on_click=lambda: _validate_config(),
                ).props("color=positive")
                ui.button(
                    "Run Pipeline",
                    icon="play_arrow",
                    on_click=lambda: _go_run(),
                ).props("color=primary")

            # Validation output
            global _validation_label
            _validation_label = ui.label("").classes("text-sm")


_validation_label = None


def _format_json() -> str:
    try:
        config = RunConfig(**app_state.config_data)
        return config.model_dump_json(indent=2)
    except Exception:
        return json.dumps(app_state.config_data, indent=2, default=str)


def _update_field(key: str, value) -> None:
    app_state.config_data[key] = value


def _update_nested(section: str, key: str, value) -> None:
    if section not in app_state.config_data:
        app_state.config_data[section] = {}
    app_state.config_data[section][key] = value


def _update_provider_type(ptype: str) -> None:
    if "provider" not in app_state.config_data:
        app_state.config_data["provider"] = {}
    app_state.config_data["provider"]["type"] = ptype
    if not app_state.config_data["provider"].get("model"):
        app_state.config_data["provider"]["model"] = DEFAULT_MODELS.get(ptype, "")


def _parse_id_list(text: str) -> list[int]:
    if not text.strip():
        return []
    try:
        return [int(x.strip()) for x in text.split(",") if x.strip()]
    except ValueError:
        return []


def _load_config(path_str: str) -> None:
    path = Path(path_str)
    if not path.exists():
        ui.notify(f"File not found: {path}", type="negative")
        return
    try:
        data = json.loads(path.read_text())
        config = RunConfig(**data)
        app_state.config_data = json.loads(config.model_dump_json())
        app_state.config_path = str(path)
        ui.notify(f"Loaded config: {path}", type="positive")
        ui.navigate.to("/config")  # refresh page
    except Exception as e:
        ui.notify(f"Invalid config: {e}", type="negative")


def _save_config(path_str: str) -> None:
    try:
        config = RunConfig(**app_state.config_data)
        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(config.model_dump_json(indent=2))
        app_state.config_path = str(path)
        ui.notify(f"Saved config: {path}", type="positive")
    except Exception as e:
        ui.notify(f"Cannot save: {e}", type="negative")


def _new_config() -> None:
    default = RunConfig()
    app_state.config_data = json.loads(default.model_dump_json())
    app_state.config_path = ""
    ui.navigate.to("/config")


def _validate_config() -> None:
    try:
        RunConfig(**app_state.config_data)
        ui.notify("Configuration is valid!", type="positive")
        if _validation_label:
            _validation_label.text = "Valid configuration"
            _validation_label.classes(replace="text-sm text-green-400")
    except Exception as e:
        ui.notify(f"Validation error: {e}", type="negative")
        if _validation_label:
            _validation_label.text = f"Invalid: {e}"
            _validation_label.classes(replace="text-sm text-red-400")


def _go_run() -> None:
    try:
        RunConfig(**app_state.config_data)
        ui.navigate.to("/pipeline")
    except Exception as e:
        ui.notify(f"Fix config errors first: {e}", type="negative")
