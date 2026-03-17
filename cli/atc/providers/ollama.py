"""Ollama (local LLM) provider for feature file generation."""

from __future__ import annotations

import base64
from pathlib import Path

import httpx

from atc.providers.base import GenerationProvider


class OllamaProvider(GenerationProvider):
    """Generate feature files using a local Ollama instance."""

    def __init__(self, model: str = "llama3", base_url: str = "http://localhost:11434") -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")

    async def generate(self, prompt: str, images: list[Path] | None = None) -> str:
        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }

        # Add images for multimodal models (e.g., llava, bakllava)
        if images:
            image_data = []
            for img_path in images:
                if img_path.exists() and img_path.stat().st_size > 0:
                    data = base64.standard_b64encode(img_path.read_bytes()).decode()
                    image_data.append(data)
            if image_data:
                payload["images"] = image_data

        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(f"{self._base_url}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()

        result = data.get("response", "")

        # Clean up markdown wrapping if present
        from atc.providers.claude import _extract_feature_content

        return _extract_feature_content(result)
