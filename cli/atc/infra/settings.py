"""Environment variable settings."""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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
