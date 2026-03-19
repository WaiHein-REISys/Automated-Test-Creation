"""Abstract base class for AI generation providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from atc.core.models import PromptBundle


class GenerationProvider(ABC):
    """Interface for feature file generation providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str | PromptBundle,
        images: list[Path] | None = None,
    ) -> str:
        """Generate a .feature file from a prompt.

        Args:
            prompt: Either a single prompt string (legacy) or a PromptBundle
                    with system_message + user_message for multi-stage generation.
            images: Optional list of image paths for vision-capable providers.

        Returns:
            The generated .feature file content.
        """

    @staticmethod
    def _resolve_prompt(prompt: str | PromptBundle) -> tuple[str, str]:
        """Split a prompt into (system_message, user_message).

        If a plain string is passed, the system message is empty and the
        entire string becomes the user message (backward compatible).
        """
        if isinstance(prompt, PromptBundle):
            return prompt.system_message, prompt.user_message
        return "", prompt
