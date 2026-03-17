"""Run configuration models."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    """AI provider configuration."""

    type: str = Field(default="prompt_only", description="claude | azure_openai | ollama | cli_agent | prompt_only")
    model: str = ""
    options: dict[str, str] = Field(default_factory=dict)


class RunOptions(BaseModel):
    """Runtime options."""

    dry_run: bool = False
    download_attachments: bool = True
    include_images_in_prompt: bool = True


class RunConfig(BaseModel):
    """Top-level run configuration loaded from JSON."""

    url: str = Field(default="", description="ADO work item URL (auto-parses org/project/ID)")
    product_name: str = Field(default="", description="Product name for folder structure")
    workspace_dir: Path = Field(default=Path("./workspace"))
    target_repo_path: Path | None = Field(
        default=None, description="Local path to target automation repo"
    )
    branch_name: str | None = Field(
        default=None, description="Git branch name, e.g. dev/DME/feature/EHB"
    )
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    options: RunOptions = Field(default_factory=RunOptions)
