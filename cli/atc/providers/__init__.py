"""Provider factory — creates the appropriate AI provider based on config."""

from __future__ import annotations

from atc.infra.config import ProviderConfig
from atc.infra.settings import AtcSettings
from atc.providers.base import GenerationProvider


def create_provider(config: ProviderConfig, settings: AtcSettings) -> GenerationProvider:
    """Create a generation provider based on configuration."""
    provider_type = config.type.lower()

    if provider_type == "claude":
        from atc.providers.claude import ClaudeProvider

        api_key = settings.anthropic_api_key.get_secret_value()
        if not api_key:
            raise ValueError(
                "ATC_ANTHROPIC_API_KEY environment variable is required for the Claude provider."
            )
        model = config.model or "claude-sonnet-4-20250514"
        return ClaudeProvider(api_key=api_key, model=model)

    elif provider_type == "azure_openai":
        from atc.providers.azure_openai import AzureOpenAIProvider

        endpoint = config.options.get("endpoint", "") or settings.azure_openai_endpoint
        api_key = settings.azure_openai_api_key.get_secret_value()
        deployment = config.model or settings.azure_openai_deployment
        api_version = (
            config.options.get("api_version", "")
            or settings.azure_openai_api_version
        )

        if not endpoint:
            raise ValueError(
                "Azure OpenAI endpoint is required. Set ATC_AZURE_OPENAI_ENDPOINT "
                "or provider.options.endpoint in run.json."
            )
        if not api_key:
            raise ValueError(
                "ATC_AZURE_OPENAI_API_KEY environment variable is required "
                "for the Azure OpenAI provider."
            )
        if not deployment:
            raise ValueError(
                "Azure OpenAI deployment name is required. Set ATC_AZURE_OPENAI_DEPLOYMENT "
                "or provider.model in run.json."
            )
        return AzureOpenAIProvider(
            endpoint=endpoint,
            api_key=api_key,
            deployment=deployment,
            api_version=api_version,
        )

    elif provider_type == "ollama":
        from atc.providers.ollama import OllamaProvider

        model = config.model or settings.ollama_model
        return OllamaProvider(model=model, base_url=settings.ollama_url)

    elif provider_type == "cli_agent":
        from atc.providers.cli_agent import CliAgentProvider

        cmd = config.options.get("command", "") or settings.cli_agent_cmd
        return CliAgentProvider(command=cmd)

    elif provider_type == "prompt_only":
        from atc.providers.prompt_only import PromptOnlyProvider

        return PromptOnlyProvider()

    else:
        raise ValueError(
            f"Unknown provider type: '{provider_type}'. "
            "Valid options: claude, azure_openai, ollama, cli_agent, prompt_only"
        )
