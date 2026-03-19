"""Azure OpenAI provider for feature file generation."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from atc.core.models import PromptBundle
from atc.providers.base import GenerationProvider


class AzureOpenAIProvider(GenerationProvider):
    """Generate feature files using Azure OpenAI Service.

    Supports multi-stage prompts: system message (rules + product context)
    is sent as the system/developer message; user message (story content)
    is sent as the user message. This separation significantly improves
    output quality on smaller models like gpt-4o-mini.
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

    async def generate(
        self,
        prompt: str | PromptBundle,
        images: list[Path] | None = None,
    ) -> str:
        system_msg, user_msg = self._resolve_prompt(prompt)

        messages: list[dict] = []

        # System message — generic rules + product-tailored context
        if system_msg:
            messages.append({"role": "system", "content": system_msg})

        # User message — story content + optional images
        user_content: list[dict] = []

        if images:
            for img_path in images:
                if img_path.exists() and img_path.stat().st_size > 0:
                    media_type = mimetypes.guess_type(str(img_path))[0] or "image/png"
                    if media_type.startswith("image/"):
                        data = base64.standard_b64encode(img_path.read_bytes()).decode()
                        user_content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{data}",
                            },
                        })

        user_content.append({"type": "text", "text": user_msg})
        messages.append({"role": "user", "content": user_content})

        response = await self._client.chat.completions.create(
            model=self._deployment,
            max_tokens=8192,
            messages=messages,
        )

        result = response.choices[0].message.content or ""

        from atc.providers.claude import _extract_feature_content

        return _extract_feature_content(result)
