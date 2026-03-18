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

    # Hierarchy depth limit (0 = unlimited)
    max_depth: int = Field(
        default=0,
        description=(
            "Maximum hierarchy depth to traverse below the root work item. "
            "0 = unlimited (fetch the full tree). "
            "1 = root + its direct children only. "
            "2 = root + children + grandchildren, etc."
        ),
    )

    # Generation limits (0 = unlimited, empty list = all)
    generation_limit: int = Field(
        default=0, description="Max total feature files to generate (0 = unlimited)"
    )
    generation_limit_per_feature: int = Field(
        default=0, description="Max feature files per Feature parent folder (0 = unlimited)"
    )
    generation_only_ids: list[int] = Field(
        default_factory=list, description="Only generate for these work item IDs (empty = all)"
    )


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
    ado_api_version: str = Field(
        default="auto",
        description=(
            "Azure DevOps REST API version. "
            "'auto' probes the server and picks the best supported version (7.1, 7.0, 6.0). "
            "Set explicitly (e.g. '7.0') for on-prem servers that reject newer versions."
        ),
    )
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    options: RunOptions = Field(default_factory=RunOptions)
