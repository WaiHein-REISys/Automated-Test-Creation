"""Prompt-only provider — saves prompt for manual generation."""

from __future__ import annotations

from pathlib import Path

from atc.providers.base import GenerationProvider


class PromptOnlyProvider(GenerationProvider):
    """Does not generate — just saves the prompt for manual use.

    The user is expected to copy the prompt into their preferred tool
    (e.g., Windsurf Cascade) and place the .feature file manually.
    Use `atc run --resume` to pick up afterward.
    """

    async def generate(self, prompt: str, images: list[Path] | None = None) -> str:
        # Return empty — the executor will skip writing the .feature file
        return ""
