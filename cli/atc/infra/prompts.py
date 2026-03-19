"""Prompt renderer — renders multi-stage prompts (system + user) from Jinja2 templates.

Pipeline:
  Stage 1 (Generic):  Instructions.txt — SpecFlow rules applicable to any product.
  Stage 2 (Tailored): system-prompt.md.j2 — product name, epic/feature context,
                       step pattern references (format examples only).
  Stage 3 (Actual):   scenario-generation.md.j2 — the specific user story content.

Stages 1+2 → system message.  Stage 3 → user message.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from atc.core.models import Attachment, PromptBundle, WorkItem, WorkItemNode


def _find_configs_dir() -> Path:
    """Find the configs directory relative to the package."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        configs = parent / "configs"
        if configs.is_dir():
            return configs
    raise FileNotFoundError("Cannot find configs/ directory")


class PromptRenderer:
    """Renders multi-stage scenario generation prompts."""

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
        product_name: str = "",
    ) -> PromptBundle:
        """Render a multi-stage prompt bundle for a user story.

        Returns a PromptBundle with:
          - system_message: generic rules + product-tailored context
          - user_message:   the specific story to generate from
        """
        ancestors = ancestors or []
        images = images or []

        # Extract context from ancestor chain
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

        # ── Stage 1 + 2: System message (generic rules + tailored context) ──
        system_template = self._env.get_template("system-prompt.md.j2")
        system_message = system_template.render(
            instructions=self._instructions,
            product_name=product_name or "Unknown Product",
            epic_title=epic_title,
            feature_title=feature_title,
            common_steps=self._common_steps,
            background_steps=self._background_steps,
        )

        # ── Stage 3: User message (the actual story content) ──
        user_template = self._env.get_template("scenario-generation.md.j2")
        user_message = user_template.render(
            story_id=story.id,
            story_title=story.title,
            story_type=story.work_item_type,
            story_description=story.description or "(No description provided)",
            story_acceptance_criteria=story.acceptance_criteria or "(No acceptance criteria provided)",
            image_paths=image_paths,
        )

        return PromptBundle(
            system_message=system_message.strip(),
            user_message=user_message.strip(),
        )
