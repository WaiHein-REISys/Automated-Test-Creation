"""Prompt renderer — renders Jinja2 templates with story context."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from atc.core.models import Attachment, WorkItem, WorkItemNode


def _find_configs_dir() -> Path:
    """Find the configs directory relative to the package."""
    # Walk up from this file to find configs/
    current = Path(__file__).resolve()
    for parent in current.parents:
        configs = parent / "configs"
        if configs.is_dir():
            return configs
    raise FileNotFoundError("Cannot find configs/ directory")


class PromptRenderer:
    """Renders scenario generation prompts from Jinja2 templates."""

    def __init__(self, configs_dir: Path | None = None) -> None:
        self.configs_dir = configs_dir or _find_configs_dir()
        self.prompts_dir = self.configs_dir / "prompts"
        self.reference_dir = self.configs_dir / "reference"

        self._env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            keep_trailing_newline=True,
        )

        # Load reference files
        self._instructions = self._load_reference("Instructions.txt")
        self._common_steps = self._load_reference("Common_Steps.txt")
        self._background_steps = self._load_reference("Background_Steps.txt")

    def _load_reference(self, filename: str) -> str:
        path = self.reference_dir / filename
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        return ""

    def render_scenario_prompt(
        self,
        story: WorkItem,
        ancestors: list[WorkItemNode] | None = None,
        images: list[Attachment] | None = None,
    ) -> str:
        """Render the scenario generation prompt for a user story."""
        ancestors = ancestors or []
        images = images or []

        # Find epic and feature from ancestors
        epic_title = ""
        feature_title = ""
        for ancestor in ancestors:
            if ancestor.work_item_type == "Epic":
                epic_title = f"{ancestor.id} - {ancestor.title}"
            elif ancestor.work_item_type == "Feature":
                feature_title = f"{ancestor.id} - {ancestor.title}"

        image_paths = [
            img.local_path.name if img.local_path else img.name
            for img in images
            if img.local_path and img.local_path.exists()
        ]

        template = self._env.get_template("scenario-generation.md.j2")
        return template.render(
            instructions=self._instructions,
            epic_title=epic_title,
            feature_title=feature_title,
            story_id=story.id,
            story_title=story.title,
            story_description=story.description or "(No description provided)",
            story_acceptance_criteria=story.acceptance_criteria or "(No acceptance criteria provided)",
            common_steps=self._common_steps,
            background_steps=self._background_steps,
            image_paths=image_paths,
        )
