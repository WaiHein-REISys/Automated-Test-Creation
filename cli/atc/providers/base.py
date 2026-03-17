"""Abstract base class for AI generation providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class GenerationProvider(ABC):
    """Interface for feature file generation providers."""

    @abstractmethod
    async def generate(self, prompt: str, images: list[Path] | None = None) -> str:
        """Generate a .feature file from a prompt.

        Args:
            prompt: The rendered scenario generation prompt.
            images: Optional list of image paths for vision-capable providers.

        Returns:
            The generated .feature file content.
        """
