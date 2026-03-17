"""Azure OpenAI provider for feature file generation."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from atc.providers.base import GenerationProvider


class AzureOpenAIProvider(GenerationProvider):
    """Generate feature files using Azure OpenAI Service.

    Requires the `openai` package: uv add openai  (or: pip install openai)

    Configuration via environment variables:
        ATC_AZURE_OPENAI_ENDPOINT  — e.g. https://my-resource.openai.azure.com
        ATC_AZURE_OPENAI_API_KEY   — API key for the Azure OpenAI resource
        ATC_AZURE_OPENAI_DEPLOYMENT — deployment name (e.g. gpt-4o, gpt-4-turbo)
        ATC_AZURE_OPENAI_API_VERSION — API version (default: 2024-12-01-preview)

    Or via run.json provider config:
        {
          "provider": {
            "type": "azure_openai",
            "model": "gpt-4o",
            "options": {
              "endpoint": "https://my-resource.openai.azure.com",
              "api_version": "2024-12-01-preview"
            }
          }
        }
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment: str,
        api_version: str = "2024-12-01-preview",
    ) -> None:
        try:
            from openai import AsyncAzureOpenAI
        except ImportError:
            raise ImportError(
                "The 'openai' package is required for the Azure OpenAI provider. "
                "Install it with: uv add openai  (or: pip install openai)"
            )

        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )
        self._deployment = deployment

    async def generate(self, prompt: str, images: list[Path] | None = None) -> str:
        content: list[dict] = []

        # Add images for vision-capable models (GPT-4o, GPT-4 Turbo)
        if images:
            for img_path in images:
                if img_path.exists() and img_path.stat().st_size > 0:
                    media_type = mimetypes.guess_type(str(img_path))[0] or "image/png"
                    if media_type.startswith("image/"):
                        data = base64.standard_b64encode(img_path.read_bytes()).decode()
                        content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{data}",
                            },
                        })

        content.append({"type": "text", "text": prompt})

        response = await self._client.chat.completions.create(
            model=self._deployment,
            max_tokens=8192,
            messages=[{"role": "user", "content": content}],
        )

        result = response.choices[0].message.content or ""

        # Clean up: extract .feature content if wrapped in markdown code blocks
        from atc.providers.claude import _extract_feature_content

        return _extract_feature_content(result)
