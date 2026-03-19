"""Environment variable settings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from atc.infra.config import CredentialsConfig


class AtcSettings(BaseSettings):
    """Settings loaded from environment variables (ATC_ prefix) and .env file."""

    model_config = SettingsConfigDict(env_prefix="ATC_", env_file=".env", extra="ignore")

    ado_pat: SecretStr = SecretStr("")
    ado_api_version: str = "auto"  # "auto", "7.1", "7.0", "6.0", etc.

    # Provider-specific (optional, depending on chosen provider)
    anthropic_api_key: SecretStr = SecretStr("")
    azure_openai_endpoint: str = ""
    azure_openai_api_key: SecretStr = SecretStr("")
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = "2024-12-01-preview"
    ollama_model: str = "llama3"
    ollama_url: str = "http://localhost:11434"
    cli_agent_cmd: str = ""


def resolve_settings(
    base: AtcSettings,
    creds: CredentialsConfig | None = None,
) -> AtcSettings:
    """Return an ``AtcSettings`` with *run.json* credentials overlaid.

    Priority (highest first):
        1. ``credentials`` section of ``run.json``
        2. Environment variables / ``.env``

    Only non-empty credential values in *creds* override the base settings.
    The original *base* object is **not** mutated — a new instance is returned
    only if at least one override is applied.
    """
    if creds is None:
        return base

    overrides: dict[str, object] = {}

    # Map CredentialsConfig fields → AtcSettings fields
    _FIELD_MAP: dict[str, str] = {
        "ado_pat": "ado_pat",
        "anthropic_api_key": "anthropic_api_key",
        "azure_openai_endpoint": "azure_openai_endpoint",
        "azure_openai_api_key": "azure_openai_api_key",
        "azure_openai_deployment": "azure_openai_deployment",
        "azure_openai_api_version": "azure_openai_api_version",
        "ollama_url": "ollama_url",
        "ollama_model": "ollama_model",
        "cli_agent_cmd": "cli_agent_cmd",
    }

    _SECRET_FIELDS = {"ado_pat", "anthropic_api_key", "azure_openai_api_key"}

    for cred_field, settings_field in _FIELD_MAP.items():
        value = getattr(creds, cred_field, "")
        if value:  # non-empty string overrides
            if settings_field in _SECRET_FIELDS:
                overrides[settings_field] = SecretStr(value)
            else:
                overrides[settings_field] = value

    if not overrides:
        return base

    # Build a new AtcSettings by copying all base values, then applying overrides
    base_data = {
        field_name: getattr(base, field_name)
        for field_name in base.model_fields
    }
    base_data.update(overrides)
    return AtcSettings.model_construct(**base_data)
