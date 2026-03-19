"""Settings page — environment variables and provider configuration."""

from __future__ import annotations

import os
from pathlib import Path

from nicegui import ui


def _load_resolved_settings() -> dict[str, str]:
    """Load settings from .env + environment using Pydantic, returning resolved values.

    This ensures the UI displays what the pipeline will actually use,
    including values from .env that are NOT in ``os.environ``.
    """
    from atc.infra.settings import AtcSettings

    try:
        s = AtcSettings()
    except Exception:
        return {}

    return {
        "ATC_ADO_PAT": s.ado_pat.get_secret_value(),
        "ATC_ADO_API_VERSION": s.ado_api_version,
        "ATC_ANTHROPIC_API_KEY": s.anthropic_api_key.get_secret_value(),
        "ATC_AZURE_OPENAI_ENDPOINT": s.azure_openai_endpoint,
        "ATC_AZURE_OPENAI_API_KEY": s.azure_openai_api_key.get_secret_value(),
        "ATC_AZURE_OPENAI_DEPLOYMENT": s.azure_openai_deployment,
        "ATC_AZURE_OPENAI_API_VERSION": s.azure_openai_api_version,
        "ATC_OLLAMA_URL": s.ollama_url,
        "ATC_OLLAMA_MODEL": s.ollama_model,
        "ATC_CLI_AGENT_CMD": s.cli_agent_cmd,
    }


def render() -> None:
    """Render the settings page."""
    ui.label("Settings").classes("text-3xl font-bold")

    resolved = _load_resolved_settings()

    # Environment file
    with ui.card().classes("w-full"):
        ui.label("Environment File").classes("font-semibold text-blue-400")
        ui.label(
            "ATC reads environment variables with the ATC_ prefix. "
            "You can also set them in a .env file."
        ).classes("text-sm text-slate-400")

        env_path = Path(".env")
        if env_path.exists():
            ui.label(f"Found: {env_path.resolve()}").classes("text-sm text-green-400")
        else:
            ui.label("No .env file found in current directory.").classes("text-sm text-yellow-400")

    # ADO Settings
    with ui.card().classes("w-full"):
        ui.label("Azure DevOps").classes("font-semibold text-blue-400")

        ado_pat = resolved.get("ATC_ADO_PAT", "")
        pat_input = ui.input(
            "ADO Personal Access Token (ATC_ADO_PAT)",
            value="***" if ado_pat else "",
            password=True,
            password_toggle_button=True,
        ).classes("w-full")

        with ui.row().classes("gap-2"):
            ui.button(
                "Test ADO Connection",
                icon="link",
                on_click=lambda: _test_ado_connection(pat_input.value),
            ).props("outlined")
            ui.button(
                "Save to .env",
                icon="save",
                on_click=lambda: _save_env_var("ATC_ADO_PAT", pat_input.value),
            ).props("outlined")

    # Provider API Keys
    with ui.card().classes("w-full"):
        ui.label("Provider API Keys").classes("font-semibold text-blue-400")

        # Claude / Anthropic
        with ui.expansion("Anthropic (Claude)", icon="smart_toy").classes("w-full"):
            anthropic_key = resolved.get("ATC_ANTHROPIC_API_KEY", "")
            anthropic_input = ui.input(
                "Anthropic API Key (ATC_ANTHROPIC_API_KEY)",
                value="***" if anthropic_key else "",
                password=True,
                password_toggle_button=True,
            ).classes("w-full")
            ui.button(
                "Save to .env",
                icon="save",
                on_click=lambda: _save_env_var("ATC_ANTHROPIC_API_KEY", anthropic_input.value),
            ).props("outlined dense")

        # Azure OpenAI
        with ui.expansion("Azure OpenAI", icon="cloud").classes("w-full"):
            az_endpoint = resolved.get("ATC_AZURE_OPENAI_ENDPOINT", "")
            az_key = resolved.get("ATC_AZURE_OPENAI_API_KEY", "")
            az_deployment = resolved.get("ATC_AZURE_OPENAI_DEPLOYMENT", "")

            az_endpoint_input = ui.input(
                "Endpoint (ATC_AZURE_OPENAI_ENDPOINT)",
                value=az_endpoint,
            ).classes("w-full")
            az_key_input = ui.input(
                "API Key (ATC_AZURE_OPENAI_API_KEY)",
                value="***" if az_key else "",
                password=True,
                password_toggle_button=True,
            ).classes("w-full")
            az_deploy_input = ui.input(
                "Deployment (ATC_AZURE_OPENAI_DEPLOYMENT)",
                value=az_deployment,
            ).classes("w-full")

            ui.button(
                "Save All to .env",
                icon="save",
                on_click=lambda: _save_multiple_env({
                    "ATC_AZURE_OPENAI_ENDPOINT": az_endpoint_input.value,
                    "ATC_AZURE_OPENAI_API_KEY": az_key_input.value,
                    "ATC_AZURE_OPENAI_DEPLOYMENT": az_deploy_input.value,
                }),
            ).props("outlined dense")

        # Ollama
        with ui.expansion("Ollama (Local)", icon="computer").classes("w-full"):
            ollama_url = resolved.get("ATC_OLLAMA_URL", "http://localhost:11434")
            ollama_model = resolved.get("ATC_OLLAMA_MODEL", "llama3")

            ollama_url_input = ui.input(
                "Ollama URL (ATC_OLLAMA_URL)",
                value=ollama_url,
            ).classes("w-full")
            ollama_model_input = ui.input(
                "Model (ATC_OLLAMA_MODEL)",
                value=ollama_model,
            ).classes("w-full")

            ui.button(
                "Save to .env",
                icon="save",
                on_click=lambda: _save_multiple_env({
                    "ATC_OLLAMA_URL": ollama_url_input.value,
                    "ATC_OLLAMA_MODEL": ollama_model_input.value,
                }),
            ).props("outlined dense")

    # Current environment status
    with ui.card().classes("w-full"):
        ui.label("Environment Status").classes("font-semibold text-blue-400")
        ui.label(
            "Shows resolved values from environment variables and .env file."
        ).classes("text-xs text-slate-400 mb-1")

        env_vars = [
            ("ATC_ADO_PAT", "Required"),
            ("ATC_ADO_API_VERSION", "Optional"),
            ("ATC_ANTHROPIC_API_KEY", "For Claude provider"),
            ("ATC_AZURE_OPENAI_ENDPOINT", "For Azure OpenAI"),
            ("ATC_AZURE_OPENAI_API_KEY", "For Azure OpenAI"),
            ("ATC_AZURE_OPENAI_DEPLOYMENT", "For Azure OpenAI"),
            ("ATC_OLLAMA_URL", "For Ollama"),
            ("ATC_OLLAMA_MODEL", "For Ollama"),
            ("ATC_CLI_AGENT_CMD", "For CLI agent"),
        ]

        for var_name, purpose in env_vars:
            value = resolved.get(var_name, "")
            with ui.row().classes("items-center gap-2"):
                if value:
                    ui.icon("check_circle").classes("text-green-400 text-sm")
                else:
                    ui.icon("radio_button_unchecked").classes("text-slate-500 text-sm")
                ui.label(var_name).classes("font-mono text-sm")
                ui.label(f"({purpose})").classes("text-xs text-slate-400")


def _test_ado_connection(pat: str) -> None:
    """Test the ADO connection with the provided PAT."""
    if not pat or pat == "***":
        ui.notify("Enter a PAT to test the connection.", type="warning")
        return
    # We can't easily do an async test here, so just validate the PAT format
    if len(pat) < 10:
        ui.notify("PAT seems too short. Check your token.", type="negative")
    else:
        ui.notify("PAT format looks valid. Use 'Run Pipeline' to test the full connection.", type="info")


def _save_env_var(key: str, value: str) -> None:
    """Save a single environment variable to .env file."""
    if value == "***":
        ui.notify("Enter the actual value (not masked) before saving.", type="warning")
        return
    _save_multiple_env({key: value})


def _save_multiple_env(vars: dict[str, str]) -> None:
    """Save multiple environment variables to .env file and update os.environ."""
    env_path = Path(".env")

    # Read existing
    existing: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                v = v.strip()
                # Strip surrounding quotes (double or single)
                if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                    v = v[1:-1]
                existing[k.strip()] = v

    # Update
    saved_count = 0
    for key, value in vars.items():
        if value and value != "***":
            existing[key] = value
            # Also update os.environ so the running process sees the change
            # immediately (e.g. when executor creates AtcSettings())
            os.environ[key] = value
            saved_count += 1

    # Write back with proper quoting
    lines = [f'{k}="{v}"' for k, v in sorted(existing.items())]
    env_path.write_text("\n".join(lines) + "\n")
    ui.notify(f"Saved {saved_count} variable(s) to .env", type="positive")
