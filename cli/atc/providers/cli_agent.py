"""External CLI agent provider for feature file generation."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from atc.providers.base import GenerationProvider


class CliAgentProvider(GenerationProvider):
    """Generate feature files by invoking an external CLI tool."""

    def __init__(self, command: str) -> None:
        """Args:
            command: Shell command template. Use {prompt_file} as placeholder
                     for the path to a temp file containing the prompt.
                     Example: "windsurf generate --prompt {prompt_file}"
        """
        if not command:
            raise ValueError("CLI agent command is required. Set ATC_CLI_AGENT_CMD.")
        self._command = command

    async def generate(self, prompt: str, images: list[Path] | None = None) -> str:
        # Write prompt to a temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(prompt)
            prompt_file = f.name

        # Substitute {prompt_file} in command
        cmd = self._command.replace("{prompt_file}", prompt_file)

        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        # Clean up temp file
        Path(prompt_file).unlink(missing_ok=True)

        if proc.returncode != 0:
            error_msg = stderr.decode(errors="replace") if stderr else "Unknown error"
            raise RuntimeError(f"CLI agent command failed (exit {proc.returncode}): {error_msg}")

        result = stdout.decode(errors="replace")

        from atc.providers.claude import _extract_feature_content

        return _extract_feature_content(result)
