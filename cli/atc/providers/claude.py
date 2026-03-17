"""Claude API provider for feature file generation."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from atc.providers.base import GenerationProvider


class ClaudeProvider(GenerationProvider):
    """Generate feature files using Anthropic's Claude API."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "The 'anthropic' package is required for the Claude provider. "
                "Install it with: uv add anthropic  (or: pip install anthropic)"
            )
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def generate(self, prompt: str, images: list[Path] | None = None) -> str:
        content: list[dict] = []

        # Add images if provided (vision)
        if images:
            for img_path in images:
                if img_path.exists() and img_path.stat().st_size > 0:
                    media_type = mimetypes.guess_type(str(img_path))[0] or "image/png"
                    if media_type.startswith("image/"):
                        data = base64.standard_b64encode(img_path.read_bytes()).decode()
                        content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": data,
                            },
                        })

        content.append({"type": "text", "text": prompt})

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=8192,
            messages=[{"role": "user", "content": content}],
        )

        # Extract text from response
        result = ""
        for block in response.content:
            if hasattr(block, "text"):
                result += block.text

        # Clean up: extract just the feature file content if wrapped in markdown
        result = _extract_feature_content(result)
        return result


def _extract_feature_content(text: str) -> str:
    """Extract .feature content from potentially markdown-wrapped response."""
    lines = text.strip().split("\n")

    # If the response starts with ```gherkin or ```feature, extract the content
    if lines and lines[0].strip().startswith("```"):
        # Find closing ```
        end_idx = len(lines) - 1
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end_idx = i
                break
        return "\n".join(lines[1:end_idx]).strip()

    return text.strip()
