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

            # Credentials (inline in run.json)
            with ui.card().classes("w-full"):
                ui.label("Credentials").classes("font-semibold text-blue-400")
                ui.label(
                    "Optional — override env vars / .env.  Leave empty to use environment."
                ).classes("text-xs text-slate-400 mb-1")

                creds_data = app_state.config_data.get("credentials", {})

                ui.input(
                    "ADO PAT",
                    value=creds_data.get("ado_pat", ""),
                    password=True,
                    password_toggle_button=True,
                    placeholder="Leave empty to use ATC_ADO_PAT env var",
                ).classes("w-full").on(
                    "change",
                    lambda e: _update_nested("credentials", "ado_pat", e.sender.value),
                )

                with ui.expansion("Provider API Keys", icon="key").classes("w-full"):
                    ui.input(
                        "Anthropic API Key",
                        value=creds_data.get("anthropic_api_key", ""),
                        password=True,
                        password_toggle_button=True,
                    ).classes("w-full").on(
                        "change",
                        lambda e: _update_nested("credentials", "anthropic_api_key", e.sender.value),
                    )

                    ui.input(
                        "Azure OpenAI Endpoint",
                        value=creds_data.get("azure_openai_endpoint", ""),
                        placeholder="https://your-resource.openai.azure.com/",
                    ).classes("w-full").on(
                        "change",
                        lambda e: _update_nested("credentials", "azure_openai_endpoint", e.sender.value),
                    )
                    ui.input(
                        "Azure OpenAI API Key",
                        value=creds_data.get("azure_openai_api_key", ""),
                        password=True,
                        password_toggle_button=True,
                    ).classes("w-full").on(
                        "change",
                        lambda e: _update_nested("credentials", "azure_openai_api_key", e.sender.value),
                    )
                    ui.input(
                        "Azure OpenAI Deployment",
                        value=creds_data.get("azure_openai_deployment", ""),
                        placeholder="gpt-4o",
                    ).classes("w-full").on(
                        "change",
                        lambda e: _update_nested("credentials", "azure_openai_deployment", e.sender.value),
                    )

                    ui.input(
                        "Ollama URL",
                        value=creds_data.get("ollama_url", ""),
                        placeholder="http://localhost:11434",
                    ).classes("w-full").on(
                        "change",
                        lambda e: _update_nested("credentials", "ollama_url", e.sender.value),
                    )
                    ui.input(
                        "Ollama Model",
                        value=creds_data.get("ollama_model", ""),
                        placeholder="llama3",
                    ).classes("w-full").on(
                        "change",
                        lambda e: _update_nested("credentials", "ollama_model", e.sender.value),
                    )

                    ui.input(
                        "CLI Agent Command",
                        value=creds_data.get("cli_agent_cmd", ""),
                        placeholder="windsurf generate --prompt {prompt_file}",
                    ).classes("w-full").on(
                        "change",
                        lambda e: _update_nested("credentials", "cli_agent_cmd", e.sender.value),
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
                ui.switch(
                    "Skip Incomplete Stories",
                    value=options_data.get("skip_incomplete_stories", False),
                    on_change=lambda e: _update_nested(
                        "options", "skip_incomplete_stories", e.value
                    ),
                ).tooltip(
                    "Skip stories that lack the minimum context for feature "
                    "generation — must contain a user/actor, goal/action, "
                    "and benefit/purpose"
                )

                ui.number(
                    "Max Hierarchy Depth (0 = unlimited)",
                    value=options_data.get("max_depth", 0),
                    min=0,
                ).classes("w-full").on(
                    "change",
                    lambda e: _update_nested(
                        "options", "max_depth", int(e.sender.value or 0)
                    ),
                )

                ui.input(
                    "Filter Tags (comma-separated, empty = fetch all children)",
                    value=", ".join(options_data.get("filter_tags", [])),
                    placeholder="e.g. Automated, SF424, PriorApproval",
                ).classes("w-full").on(
                    "change",
                    lambda e: _update_nested(
                        "options",
                        "filter_tags",
                        _parse_tag_list(e.sender.value),
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

            # Test Execution
            with ui.card().classes("w-full"):
                ui.label("Test Execution (EHB Runner)").classes("font-semibold text-blue-400")
                ui.label(
                    "Run generated tests using the EHB Test Runner.  "
                    "Uses target_repo_path as the EHB2010 project root."
                ).classes("text-xs text-slate-400 mb-1")

                test_exec_data = options_data.get("test_execution", {})

                ui.switch(
                    "Enable Test Execution",
                    value=test_exec_data.get("enabled", False),
                    on_change=lambda e: _update_test_exec("enabled", e.value),
                )

                ui.input(
                    "SpecFlow Tag (e.g. Automated)",
                    value=test_exec_data.get("tag", ""),
                    placeholder="Leave empty to run all tests",
                ).classes("w-full").on(
                    "change",
                    lambda e: _update_test_exec("tag", e.sender.value),
                )

                ui.input(
                    "Filter Expression (overrides tag)",
                    value=test_exec_data.get("filter_expr", ""),
                    placeholder="e.g. FullyQualifiedName~PriorApproval",
                ).classes("w-full").on(
                    "change",
                    lambda e: _update_test_exec("filter_expr", e.sender.value),
                )

                with ui.expansion("Advanced Test Settings", icon="tune").classes("w-full"):
                    ui.input(
                        "Run ID (auto-generated if empty)",
                        value=test_exec_data.get("run_id", ""),
                    ).classes("w-full").on(
                        "change",
                        lambda e: _update_test_exec("run_id", e.sender.value),
                    )

                    ui.input(
                        "Results Directory",
                        value=test_exec_data.get("results_dir", ""),
                        placeholder="./TestResults",
                    ).classes("w-full").on(
                        "change",
                        lambda e: _update_test_exec("results_dir", e.sender.value),
                    )

                    ui.select(
                        ["Release", "Debug"],
                        value=test_exec_data.get("config", "Release"),
                        label="Build Configuration",
                    ).classes("w-full").on(
                        "change",
                        lambda e: _update_test_exec("config", e.sender.value),
                    )

                    ui.switch(
                        "Auto Build Before Tests",
                        value=test_exec_data.get("auto_build", True),
                        on_change=lambda e: _update_test_exec("auto_build", e.value),
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


def _update_test_exec(key: str, value) -> None:
    """Update a field inside options.test_execution."""
    if "options" not in app_state.config_data:
        app_state.config_data["options"] = {}
    if "test_execution" not in app_state.config_data["options"]:
        app_state.config_data["options"]["test_execution"] = {}
    app_state.config_data["options"]["test_execution"][key] = value


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


def _parse_tag_list(text: str) -> list[str]:
    """Parse a comma-separated list of tag strings."""
    if not text.strip():
        return []
    return [t.strip() for t in text.split(",") if t.strip()]


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
